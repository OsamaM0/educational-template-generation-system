#!/usr/bin/env python3
"""ETGS results dashboard — run the tahdiri -> AI cycle and browse the results.

Single-file, stdlib-only UI on http://0.0.0.0:2007/ :
  * Run panel: start `questions_cycle.py` (templates / workers / limit) and tail its log
  * Results browser: per-lesson summaries / worksheets / questions / mind maps
    straight from the `ai` database (search by lesson name or idx)

Usage:
    python3 results_dashboard.py --port 2007
"""
import argparse
from collections import Counter
import json
import os
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT))

from clients.mongo_client import MongoDBClient  # noqa: E402
from kp.config import Settings as KnowledgeSettings
from utils.run_progress import PREFIX, read_progress

LOG_DIR = ROOT / "logs"
RUN_LOG = LOG_DIR / "ui_run.log"
TEMPLATE_NAMES = ("summaries", "worksheets", "questions", "mindmaps", "knowledge_productions")
IDENTITY_FIELDS = {"document_uuid": 1, "document_idx": 1, "filename": 1, "generated_at": 1}
INDEX_TTL_SECONDS = 60
RUN_LOG_TAIL_LINES = 60

# ---------------------------------------------------------------- MongoDB ---

_mongo = None
_index_cache = {"at": 0.0, "lessons": []}
_index_lock = threading.Lock()
_backfill_cache = {"key": None, "at": 0.0, "value": None}
_backfill_lock = threading.Lock()
_journal_cache = {"path": None, "offset": 0, "counts": Counter(),
                  "totals": Counter(), "recent": []}


def get_mongo() -> MongoDBClient:
    """Return a connected client, retrying once on flaky connections."""
    global _mongo
    if _mongo is not None and _mongo.storage_db is not None:
        return _mongo
    client = MongoDBClient()
    if not client.connect():
        if not client.connect():  # one retry: the remote link is flaky
            raise ConnectionError('MongoDB is unavailable; lesson results will refresh after it reconnects')
    _mongo = client
    return client


def lesson_index(query: str = "") -> list:
    """Build a cached lesson index with presence and knowledge status."""
    query = (query or '').strip()
    with _index_lock:
        now = time.time()
        if now - _index_cache.get("at", 0) >= INDEX_TTL_SECONDS:
            mongo = get_mongo()
            lessons = {}
            for doc in mongo.storage_db["summaries"].find({}, IDENTITY_FIELDS):
                uuid = doc.get("document_uuid")
                if uuid:
                    lessons[uuid] = {
                        "uuid": uuid, "idx": doc.get("document_idx"),
                        "filename": doc.get("filename"), "generated_at": doc.get("generated_at"),
                        "templates": ["summaries"], "knowledge_status": "missing",
                        "goal_count": None, "product_count": 0,
                    }
            # The status filter needs only the destination collection; other
            # template presence is fetched for the requested page below.
            for doc in mongo.storage_db[collection_name("knowledge_productions")].find(
                    {}, {"document_uuid": 1, "failed_goals": 1, "products.goal_id": 1}):
                entry = lessons.get(doc.get("document_uuid"))
                if entry:
                    entry["templates"].append("knowledge_productions")
                    entry["knowledge_status"] = "partial" if doc.get("failed_goals") else "complete"
                    entry["product_count"] = len(doc.get("products") or [])
            def sort_key(entry):
                idx = str(entry.get("idx") or "")
                return (0, int(idx)) if idx.isdigit() else (1, idx)

            ordered = sorted(lessons.values(), key=sort_key)
            _index_cache.update(at=now, lessons=ordered)
        rows = _index_cache["lessons"]
        if not query:
            return rows
        needle = query.casefold()
        return [row for row in rows if (str(row.get("idx") or "") == query if query.isdigit() else
                needle in str(row.get("idx") or "").casefold())
                or needle in str(row.get("filename") or "").casefold()]


def lesson_page(query: str = "", status: str = "all", page: int = 1, page_size: int = 40) -> dict:
    if status not in {"all", "complete", "partial", "missing"}:
        raise ValueError("invalid knowledge status filter")
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    rows = lesson_index(query)
    if status != "all":
        rows = [row for row in rows if row["knowledge_status"] == status]
    total = len(rows)
    items = [dict(row, templates=list(row["templates"])) for row in rows[(page - 1) * page_size:page * page_size]]
    if items:
        mongo = get_mongo()
        by_uuid = {item["uuid"]: item for item in items}
        lookup = {"document_uuid": {"$in": list(by_uuid)}}
        for name in ("worksheets", "questions", "mindmaps"):
            projection = {"document_uuid": 1}
            if name == "worksheets":
                projection["worksheet.goals"] = 1
            for doc in mongo.storage_db[name].find(lookup, projection):
                item = by_uuid.get(doc.get("document_uuid"))
                if item:
                    item["templates"].append(name)
                    if name == "worksheets":
                        item["goal_count"] = len((doc.get("worksheet") or {}).get("goals") or [])
    return {"items": items,
            "total": total, "page": page, "page_size": page_size,
            "pages": max(1, (total + page_size - 1) // page_size)}


def filter_lessons(query: str) -> list:
    """Filter the lesson index by filename substring or idx."""
    return lesson_index(query)


def lesson_stats() -> dict:
    mongo = get_mongo()
    counts = {name: mongo.storage_db[collection_name(name)].count_documents({})
              for name in TEMPLATE_NAMES}
    # Collection counts are exact. Their maximum is a cheap lower bound for
    # lessons when some legacy lessons exist in only one collection.
    return {"lessons": max(counts.values(), default=0), "counts": counts}


def lesson_detail(uuid: str) -> dict:
    """Full stored records for one lesson, one per template collection."""
    mongo = get_mongo()
    detail = {}
    for name in TEMPLATE_NAMES:
        detail[name] = mongo.storage_db[collection_name(name)].find_one({"document_uuid": uuid})
    return detail


def collection_name(name):
    return KnowledgeSettings().col_knowledge if name == "knowledge_productions" else name

# ------------------------------------------------------------- run control ---

run_lock = threading.Lock()
run_proc = {"proc": None, "log": None, "cmd": [], "started_at": None}

ALLOWED_TEMPLATE_CHOICES = set(TEMPLATE_NAMES)


def _tail_lines(path: Path, max_bytes: int = 131072) -> list[str]:
    try:
        with path.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(max(0, size - max_bytes))
            data = stream.read().decode("utf-8", errors="replace")
        lines = data.splitlines()
        return lines[1:] if size > max_bytes else lines
    except OSError:
        return []


def _backfill_running() -> bool:
    try:
        pid = int((LOG_DIR / "kp-backfill.pid").read_text().strip())
        command = Path(f"/proc/{pid}/cmdline").read_bytes()
        return b"knowledge_production.py" in command and b"--all" in command
    except (OSError, ValueError):
        return False


def backfill_status() -> dict:
    """Summarize a detached all-lesson run without loading its growing log."""
    logs = sorted(LOG_DIR.glob("kp-backfill-*.log"), key=lambda p: p.stat().st_mtime)
    if not logs:
        return {"available": False, "running": False}
    log = logs[-1]
    journal = log.with_suffix(".jsonl")
    report = log.with_suffix(".json")
    running = _backfill_running()
    key = (str(log), log.stat().st_size,
           journal.stat().st_size if journal.exists() else 0, running)
    with _backfill_lock:
        if (_backfill_cache["key"] == key and time.time() - _backfill_cache["at"] < 5):
            return _backfill_cache["value"]
        if _journal_cache["path"] != journal or (journal.exists() and journal.stat().st_size < _journal_cache["offset"]):
            _journal_cache.update(path=journal, offset=0, counts=Counter(), totals=Counter(), recent=[])
        if journal.exists():
            with journal.open(encoding="utf-8") as stream:
                stream.seek(_journal_cache["offset"])
                while True:
                    position = stream.tell()
                    line = stream.readline()
                    if not line:
                        break
                    if not line.endswith("\n"):
                        stream.seek(position)
                        break
                    try:
                        item = json.loads(line)
                    except ValueError:
                        continue
                    result, usage = item.get("result") or {}, item.get("usage") or {}
                    _journal_cache["counts"][result.get("status", "unknown")] += 1
                    for field in ("calls", "input_tokens", "cached_tokens", "output_tokens", "total_tokens"):
                        _journal_cache["totals"][field] += usage.get(field, 0) or 0
                    _journal_cache["totals"]["estimated_cost_usd"] += usage.get("estimated_cost_usd", 0) or 0
                    _journal_cache["recent"] = (_journal_cache["recent"] + [{
                        "lesson_id": result.get("document_idx") or result.get("lesson_id"),
                        "title": result.get("title"), "status": result.get("status"),
                        "products": result.get("products", 0),
                        "failed_goals": len(result.get("failed_goals") or [])}])[-6:]
                _journal_cache["offset"] = stream.tell()
        counts = _journal_cache["counts"]
        totals = _journal_cache["totals"]
        recent = _journal_cache["recent"]
        first = []
        try:
            with log.open(encoding="utf-8", errors="replace") as stream:
                for _, line in zip(range(3), stream):
                    first.append(line)
        except OSError:
            pass
        total = 0
        for line in first:
            if line.startswith(PREFIX):
                try:
                    event = json.loads(line[len(PREFIX):])
                    if event.get("event") == "run_started":
                        total = int(event.get("total") or 0)
                        break
                except (ValueError, TypeError):
                    pass
        events = []
        for line in _tail_lines(log):
            if line.startswith(PREFIX):
                try:
                    event = json.loads(line[len(PREFIX):])
                    if event.get("event") in {"stage", "lesson_completed", "run_finished"}:
                        events.append(event)
                except ValueError:
                    pass
        active = {}
        for event in events:
            lesson_id = str(event.get("lesson_id") or "")
            if event.get("event") == "lesson_completed":
                active.pop(lesson_id, None)
            elif event.get("event") == "stage":
                active[lesson_id] = event
        value = {"available": True, "running": running, "total": total,
                 "completed": sum(counts.values()), "counts": dict(counts),
                 "usage": {**totals, "estimated_cost_usd": round(totals["estimated_cost_usd"], 6)},
                 "recent": list(reversed(recent)), "active": list(active.values())[-8:],
                 "log": log.name, "report_ready": report.exists()}
        _backfill_cache.update(key=key, at=time.time(), value=value)
        return value


def build_run_command(payload: dict) -> list:
    """Route stored-content KP backfills or a cycle filling multiple templates."""
    if not isinstance(payload, dict):
        raise ValueError("run request must be an object")
    if payload.get('resume_pending'):
        cmd = [sys.executable or 'python3', '-u', 'knowledge_production.py',
               '--resume-pending', str(LOG_DIR / 'pending-knowledge-productions')]
        if payload.get('dry_run'):
            cmd.append('--dry-run')
        return cmd
    selected = payload.get("templates")
    if not isinstance(selected, list) or not selected or any(
            not isinstance(t, str) or t not in ALLOWED_TEMPLATE_CHOICES for t in selected):
        raise ValueError("select valid templates")
    templates = list(dict.fromkeys(selected))
    try:
        workers = max(1, min(int(payload.get("workers") or 2), 64))
        limit = int(payload.get("limit") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("workers/limit must be numbers") from exc
    if limit < 0:
        raise ValueError("limit must be nonnegative")
    lesson_ids = [t for t in re.split(r"[\s,]+", str(payload.get("lesson_ids") or "").strip()) if t]
    if any(not t.isdigit() for t in lesson_ids):
        raise ValueError("lesson ids must be numbers separated by spaces or commas")
    only_knowledge = templates == ["knowledge_productions"]
    cmd = [sys.executable or "python3", "-u"]
    if only_knowledge:
        cmd += ["knowledge_production.py", "--workers", str(workers)]
        cmd += ["--lesson-id", *lesson_ids] if lesson_ids else ["--all"]
        if payload.get("force"):
            cmd += ["--force"]
    else:
        cmd += ["questions_cycle.py", "--templates", *templates, "--workers", str(workers)]
        if lesson_ids:
            cmd += ["--lesson-source-id", *lesson_ids]
        if payload.get("force"):
            cmd += ["--force-knowledge"]
    if limit:
        cmd += ["--limit", str(limit)]
    if payload.get("dry_run"):
        cmd += ["--dry-run"]
    return cmd


def start_run(payload: dict) -> dict:
    """Start a generation run in the background; fails when one is already active."""
    cmd = build_run_command(payload)
    with run_lock:
        if backfill_status()["running"]:
            raise RuntimeError("The all-lesson knowledge run is active. Wait for it to finish before starting another run.")
        if run_proc["proc"] is not None and run_proc["proc"].poll() is None:
            raise RuntimeError("a run is already in progress")
        LOG_DIR.mkdir(exist_ok=True)
        if run_proc["log"] is not None:
            run_proc["log"].close()
        run_proc["log"] = open(RUN_LOG, "wb")
        _index_cache["at"] = 0
        run_proc["proc"] = subprocess.Popen(
            cmd, cwd=ROOT, stdout=run_proc["log"], stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        run_proc["cmd"] = cmd
        run_proc["started_at"] = time.time()
    return {"started": True, "cmd": cmd}


def run_status() -> dict:
    proc = run_proc["proc"]
    running = proc is not None and proc.poll() is None
    lines = []
    try:
        lines = RUN_LOG.read_text(errors="replace").splitlines()
    except OSError:
        pass
    progress = read_progress(lines)
    code = (proc.poll() if proc is not None else
            int(progress['failed'] > 0 or progress.get('final_status') in {'empty', 'no_content'})
            if progress['finished'] else None)
    if proc is not None and not running:
        _index_cache["at"] = 0
    tail = []
    for line in lines:
        if line.startswith(PREFIX):
            try:
                event = json.loads(line[len(PREFIX):])
                fields = ("event", "lesson_id", "template", "goal_id", "stage", "state", "status",
                          "total", "reason", "attempt", "error", "wait_seconds", "max_tokens",
                          "errors", "failed_goals")
                line = " · ".join(f"{k}={event[k]}" for k in fields if event.get(k) not in (None, []))
            except ValueError:
                continue
        if line:
            tail.append(line)
    return {"running": running, "cmd": run_proc["cmd"], "tail": tail[-RUN_LOG_TAIL_LINES:],
            "exit_code": code, "progress": progress,
            "elapsed_seconds": int(time.time() - run_proc["started_at"]) if run_proc.get("started_at") else 0}

# ----------------------------------------------------------------- HTML/JS ---

PAGE = (ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")

# ---------------------------------------------------------------- handlers ---


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        try:
            if parsed.path in ("/", "/index.html"):
                self._respond(200, PAGE.encode(), "text/html; charset=utf-8")
            elif parsed.path == "/api/stats":
                self._respond_json(lesson_stats())
            elif parsed.path == "/api/lessons":
                self._respond_json(lesson_page(
                    params.get("q", [""])[0], params.get("status", ["all"])[0],
                    int(params.get("page", ["1"])[0])))
            elif parsed.path == "/api/lesson":
                uuid = params.get("uuid", [""])[0]
                self._respond_json(lesson_detail(uuid) if uuid else {})
            elif parsed.path == "/api/run/status":
                self._respond_json(run_status())
            elif parsed.path == "/api/backfill/status":
                self._respond_json(backfill_status())
            else:
                self._respond(404, b"not found", "text/plain")
        except Exception as exc:  # flaky remote mongo must not kill the request
            self._respond_json({"error": str(exc)}, code=500)

    def do_POST(self):  # noqa: N802
        if urlparse(self.path).path != "/api/run":
            self._respond(404, b"not found", "text/plain")
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
            self._respond_json(start_run(payload))
        except (ValueError, RuntimeError) as exc:
            self._respond_json({"error": str(exc)}, code=400)
        except Exception as exc:
            self._respond_json({"error": str(exc)}, code=500)

    def _respond_json(self, data: dict, code: int = 200):
        body = json.dumps(data, default=str, ensure_ascii=False).encode()
        self._respond(code, body, "application/json; charset=utf-8")

    def _respond(self, code: int, body: bytes, content_type: str):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="ETGS results dashboard")
    parser.add_argument("--port", type=int, default=2007)
    args = parser.parse_args()
    LOG_DIR.mkdir(exist_ok=True)
    print(f"📚 results dashboard on http://0.0.0.0:{args.port}/", flush=True)
    ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
