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

LOG_DIR = ROOT / "logs"
RUN_LOG = LOG_DIR / "ui_run.log"
TEMPLATE_NAMES = ("summaries", "worksheets", "questions", "mindmaps")
IDENTITY_FIELDS = {"document_uuid": 1, "document_idx": 1, "filename": 1, "generated_at": 1}
INDEX_TTL_SECONDS = 30
RUN_LOG_TAIL_LINES = 60

# ---------------------------------------------------------------- MongoDB ---

_mongo = None
_index_cache = {"at": 0.0, "lessons": []}


def get_mongo() -> MongoDBClient:
    """Return a connected client, retrying once on flaky connections."""
    global _mongo
    if _mongo is not None:
        return _mongo
    client = MongoDBClient()
    if not client.connect():
        client.connect()  # one retry: the remote link is flaky
    _mongo = client
    return client


def lesson_index() -> list:
    """Identity + template-presence for every generated lesson (cached briefly)."""
    now = time.time()
    if now - _index_cache["at"] < INDEX_TTL_SECONDS and _index_cache["lessons"]:
        return _index_cache["lessons"]

    mongo = get_mongo()
    lessons = {}
    for name in TEMPLATE_NAMES:
        for doc in mongo.storage_db[name].find({}, IDENTITY_FIELDS):
            uuid = doc.get("document_uuid")
            if not uuid:
                continue
            entry = lessons.setdefault(uuid, {
                "uuid": uuid,
                "idx": doc.get("document_idx"),
                "filename": doc.get("filename"),
                "generated_at": None,
                "templates": [],
            })
            entry["templates"].append(name)
            generated_at = doc.get("generated_at")
            if generated_at and (entry["generated_at"] is None or generated_at > entry["generated_at"]):
                entry["generated_at"] = generated_at

    ordered = sorted(lessons.values(), key=lambda e: str(e.get("idx") or ""))
    _index_cache.update(at=now, lessons=ordered)
    return ordered


def filter_lessons(query: str) -> list:
    """Filter the lesson index by filename substring or idx."""
    query = (query or "").strip().lower()
    if not query:
        return lesson_index()
    return [
        entry for entry in lesson_index()
        if query in str(entry.get("filename") or "").lower()
        or query in str(entry.get("idx") or "")
    ]


def lesson_stats() -> dict:
    counts = {name: 0 for name in TEMPLATE_NAMES}
    for entry in lesson_index():
        for name in entry["templates"]:
            counts[name] += 1
    return {"lessons": len(lesson_index()), "counts": counts}


def lesson_detail(uuid: str) -> dict:
    """Full stored records for one lesson, one per template collection."""
    mongo = get_mongo()
    detail = {}
    for name in TEMPLATE_NAMES:
        detail[name] = mongo.storage_db[name].find_one({"document_uuid": uuid})
    return detail

# ------------------------------------------------------------- run control ---

run_lock = threading.Lock()
run_proc = {"proc": None, "log": None, "cmd": []}

ALLOWED_TEMPLATE_CHOICES = {"summaries", "worksheets", "questions", "mindmaps"}


def build_run_command(payload: dict) -> list:
    """Translate the run-panel form into a questions_cycle.py command line."""
    templates = [t for t in (payload.get("templates") or []) if t in ALLOWED_TEMPLATE_CHOICES]
    if not templates:
        raise ValueError("no valid templates selected")

    try:
        workers = max(1, min(int(payload.get("workers") or 2), 64))
        limit = int(payload.get("limit") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("workers/limit must be numbers") from exc

    cmd = [sys.executable or "python3", "-u", "questions_cycle.py",
           "--templates", *templates, "--workers", str(workers)]
    if limit > 0:
        cmd += ["--limit", str(limit)]

    lesson_ids = [t for t in re.split(r"[\s,]+", str(payload.get("lesson_ids") or "")) if t.isdigit()]
    if lesson_ids:
        cmd += ["--lesson-source-id", *lesson_ids]
    return cmd


def start_run(payload: dict) -> dict:
    """Start a generation run in the background; fails when one is already active."""
    cmd = build_run_command(payload)
    with run_lock:
        if run_proc["proc"] is not None and run_proc["proc"].poll() is None:
            raise RuntimeError("a run is already in progress")
        LOG_DIR.mkdir(exist_ok=True)
        run_proc["log"] = open(RUN_LOG, "wb")
        run_proc["proc"] = subprocess.Popen(
            cmd, cwd=ROOT, stdout=run_proc["log"], stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        run_proc["cmd"] = cmd
    return {"started": True, "cmd": cmd}


def run_status() -> dict:
    proc = run_proc["proc"]
    running = proc is not None and proc.poll() is None
    tail = []
    try:
        tail = RUN_LOG.read_text(errors="replace").splitlines()[-RUN_LOG_TAIL_LINES:]
    except OSError:
        pass
    return {"running": running, "cmd": run_proc["cmd"], "tail": tail}

# ----------------------------------------------------------------- HTML/JS ---

PAGE = r"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ETGS — نتائج التوليد</title>
<style>
 body{background:#0d1117;color:#c9d1d9;font:14px/1.6 system-ui,monospace;margin:0}
 header{background:#161b22;border-bottom:1px solid #30363d;padding:12px 20px;display:flex;
        gap:14px;align-items:center;flex-wrap:wrap}
 header h1{font-size:17px;color:#58a6ff;margin:0}
 .chip{background:#21262d;border:1px solid #30363d;border-radius:12px;padding:3px 10px;font-size:12px}
 .chip b{color:#58a6ff}
 a{color:#58a6ff;text-decoration:none}
 .layout{display:flex;height:calc(100vh - 58px)}
 aside{width:330px;min-width:280px;border-left:1px solid #30363d;overflow-y:auto;padding:12px}
 main{flex:1;overflow-y:auto;padding:18px 24px}
 input,select,button{background:#0d1117;color:#c9d1d9;border:1px solid #30363d;
        border-radius:6px;padding:7px 10px;font:inherit}
 button{cursor:pointer;background:#238636;border-color:#238636;color:#fff}
 button.ghost{background:#21262d;border-color:#30363d;color:#c9d1d9}
 button:disabled{opacity:.5;cursor:not-allowed}
 .panel{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px;margin-bottom:14px}
 .panel h2{font-size:13px;color:#8b949e;margin:0 0 8px}
 .checks label{display:inline-flex;gap:5px;align-items:center;margin:2px 8px 2px 0;font-size:13px}
 .row{display:flex;gap:8px;margin:8px 0}
 .row input{width:90px}
 .lesson{padding:8px 10px;border-radius:6px;cursor:pointer;display:flex;justify-content:space-between;
         align-items:center;gap:8px}
 .lesson:hover{background:#21262d}
 .lesson.active{background:#1f6feb33;border:1px solid #1f6feb}
 .lesson .name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .dots i{width:9px;height:9px;border-radius:50%;display:inline-block;margin-inline-start:3px}
 .d-sum{background:#3fb950}.d-wor{background:#58a6ff}.d-que{background:#d29922}.d-min{background:#a371f7}
 h3.sec{color:#58a6ff;font-size:15px;border-bottom:1px solid #30363d;padding-bottom:6px;margin:22px 0 10px}
 .qcard{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px 14px;margin:10px 0}
 .qcard .qt{font-weight:700;color:#e6edf3}
 .qcard ul{margin:8px 0 4px;padding-inline-start:20px}
 .qcard li{margin:3px 0}
 .qcard li.ok{color:#3fb950;font-weight:700}
 .ans{color:#3fb950;margin-top:6px}
 .goal-tag{display:inline-block;background:#21262d;border-radius:10px;padding:1px 9px;
           font-size:11px;color:#8b949e;margin-top:6px}
 .kv{margin:3px 0}
 .kv .k{color:#8b949e;font-size:12px}
 .kv .v{color:#c9d1d9}
 ul.tree{list-style:none;padding-inline-start:16px;margin:2px 0}
 ul.tree li{margin:3px 0}
 .node{background:#21262d;border-radius:6px;padding:3px 10px;display:inline-block}
 pre{background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:12px;overflow:auto;
     max-height:320px;direction:ltr;text-align:left;font-size:12px}
 .muted{color:#8b949e}
 .empty{color:#8b949e;text-align:center;padding:40px 10px}
</style></head><body>
<header>
 <h1>📚 ETGS — لوحة نتائج التوليد</h1>
 <span class="chip">الدروس <b id="s-lessons">…</b></span>
 <span class="chip">summaries <b id="s-summaries">…</b></span>
 <span class="chip">worksheets <b id="s-worksheets">…</b></span>
 <span class="chip">questions <b id="s-questions">…</b></span>
 <span class="chip">mindmaps <b id="s-mindmaps">…</b></span>
 <a href="http://localhost:2006/" target="_blank">لوحة تقدم التشغيل ↗</a>
</header>
<div class="layout">
<aside>
  <div class="panel">
    <h2>🔍 بحث</h2>
    <div class="row"><input id="q" placeholder="اسم الدرس أو رقم idx" style="flex:1">
      <button class="ghost" onclick="loadLessons()">بحث</button></div>
  </div>
  <div class="panel">
    <h2>▶️ تشغيل التوليد (questions_cycle.py)</h2>
    <div class="checks">
      <label><input type="checkbox" value="summaries" checked>summaries</label>
      <label><input type="checkbox" value="worksheets" checked>worksheets</label>
      <label><input type="checkbox" value="questions" checked>questions</label>
      <label><input type="checkbox" value="mindmaps">mindmaps</label>
    </div>
    <div class="row">
      <input id="workers" type="number" value="2" min="1" max="64" title="workers">
      <input id="limit" type="number" placeholder="limit" min="0" title="max lessons (0 = all)">
      <input id="lesson-ids" placeholder="lesson ids…" style="flex:1">
      <button id="run-btn" onclick="startRun()">تشغيل</button>
    </div>
    <pre id="run-log" class="muted">لا يوجد تشغيل بعد.</pre>
  </div>
  <div id="lesson-list"></div>
</aside>
<main id="detail"><div class="empty">اختر درساً من القائمة لعرض الملخص وورقة العمل والأسئلة وخريطة الذهن.</div></main>
</div>
<script>
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const fmtDate = (s) => s ? String(s).slice(0, 19).replace("T", " ") : "—";
const DOT = {summaries:"d-sum", worksheets:"d-wor", questions:"d-que", mindmaps:"d-min"};

async function loadStats() {
  const s = await (await fetch("/api/stats")).json();
  $("s-lessons").textContent = s.lessons;
  for (const [name, n] of Object.entries(s.counts)) $("s-" + name).textContent = n;
}

async function loadLessons() {
  const rows = await (await fetch("/api/lessons?q=" + encodeURIComponent($("q").value))).json();
  $("lesson-list").innerHTML = rows.map(e => `
    <div class="lesson" id="L-${esc(e.uuid)}" onclick="openLesson('${esc(e.uuid)}')">
      <span class="name">${esc(e.filename || "(بدون اسم)")} <span class="muted">#${esc(e.idx)}</span></span>
      <span class="dots">${e.templates.map(t => `<i class="${DOT[t]}" title="${t}"></i>`).join("")}</span>
    </div>`).join("") || `<div class="empty">لا توجد نتائج.</div>`;
}

function renderValue(v) {
  if (v === null || v === undefined || v === "") return "";
  if (Array.isArray(v)) return "<ul>" + v.map(x => `<li>${renderValue(x)}</li>`).join("") + "</ul>";
  if (typeof v === "object")
    return Object.entries(v).filter(([k]) => !k.startsWith("_")).map(([k, val]) =>
      `<div class="kv"><div class="k">${esc(k)}</div><div class="v">${renderValue(val)}</div></div>`).join("");
  return `<span class="v">${esc(String(v))}</span>`;
}

function questionCard(q, kind) {
  let body = `<div class="qt">${esc(q.question)}</div>`;
  const choices = Array.isArray(q.choices) ? q.choices : [];
  if (choices.length) {
    const correct = Number.isInteger(q.answer_key) ? q.answer_key : -1;
    body += "<ul>" + choices.map((c, i) =>
      `<li class="${i === correct ? "ok" : ""}">${esc(c)} ${i === correct ? "✔" : ""}</li>`).join("") + "</ul>";
    if (correct >= 0 && !choices[correct]) body += `<div class="ans">الإجابة: فهرس ${correct}</div>`;
  } else if (q.answer !== undefined) {
    body += `<div class="ans">الإجابة: ${esc(q.answer)}</div>`;
  }
  if (q.solution_outline) body += `<div class="kv"><div class="k">خطوات الحل</div><div class="v">${esc(q.solution_outline)}</div></div>`;
  if (q.target_goal) body += `<span class="goal-tag">🎯 ${esc(q.target_goal)}</span>`;
  return `<div class="qcard">${body}</div>`;
}

function renderQuestions(payload) {
  const groups = [["multiple_choice", "اختيار من متعدد"], ["true_false", "صح أو خطأ"],
                  ["short_answer", "إجابة قصيرة"], ["complete", "أكمل"]];
  let html = "";
  for (const [key, label] of groups) {
    const items = payload[key] || [];
    if (!items.length) continue;
    html += `<h3 class="sec">❓ ${label} (${items.length})</h3>` + items.map(q => questionCard(q, key)).join("");
  }
  return html || `<div class="muted">لا توجد أسئلة مخزنة.</div>`;
}

function mindmapTree(payload) {
  const nodes = payload.nodeDataArray, links = payload.linkDataArray;
  if (!Array.isArray(nodes) || !Array.isArray(links)) return null;
  const kids = {};
  for (const l of links) (kids[l.from] = kids[l.from] || []).push(l.to);
  const isChild = new Set(links.map(l => l.to));
  const byKey = Object.fromEntries(nodes.map(n => [n.key, n]));
  const walk = (key, depth) => {
    if (depth > 12) return "";
    const node = byKey[key] || {};
    return `<li><span class="node">${esc(node.text ?? key)}</span>` +
      (kids[key] || []).map(k => `<ul class="tree">${walk(k, depth + 1)}</ul>`).join("") + `</li>`;
  };
  return `<ul class="tree">${nodes.filter(n => !isChild.has(n.key)).map(n => walk(n.key, 0)).join("")}</ul>`;
}

function renderDetail(d) {
  const rec = (name) => d[name] || null;
  let html = "";
  const sum = rec("summaries");
  if (sum) {
    const s = sum.summary || {};
    html += `<h3 class="sec">📝 الملخص <span class="muted">${fmtDate(sum.generated_at)}</span></h3>`;
    for (const [key, label] of [["opening", "الافتتاحية"], ["summary", "الملخص"], ["ending", "الخاتمة"]])
      if (s[key]) html += `<div class="qcard"><div class="k muted">${label}</div><div dir="rtl">${esc(s[key])}</div></div>`;
  }
  const wor = rec("worksheets");
  if (wor) {
    html += `<h3 class="sec">📄 ورقة العمل <span class="muted">${fmtDate(wor.generated_at)}</span></h3>`;
    if ((wor.goals || []).length)
      html += `<div class="qcard"><div class="k muted">الأهداف</div><ul>${wor.goals.map(g => `<li>${esc(g)}</li>`).join("")}</ul></div>`;
    html += `<div class="qcard">${renderValue(wor.worksheet)}</div>`;
  }
  const que = rec("questions");
  if (que) {
    html += `<h3 class="sec">🎯 الأسئلة <span class="muted">${fmtDate(que.generated_at)}</span></h3>`;
    html += renderQuestions(que.questions || {});
  }
  const mind = rec("mindmaps");
  if (mind) {
    html += `<h3 class="sec">🧠 خريطة الذهن <span class="muted">${fmtDate(mind.generated_at)}</span></h3>`;
    const tree = mindmapTree(mind.mindmap || {});
    html += tree || `<div class="qcard">${renderValue(mind.mindmap)}</div>`;
  }
  return html || `<div class="empty">لا توجد بيانات مخزنة لهذا الدرس.</div>`;
}

async function openLesson(uuid) {
  document.querySelectorAll(".lesson").forEach(el => el.classList.remove("active"));
  const row = $("L-" + CSS.escape(uuid));
  if (row) row.classList.add("active");
  $("detail").innerHTML = `<div class="empty">جارٍ التحميل…</div>`;
  const d = await (await fetch("/api/lesson?uuid=" + encodeURIComponent(uuid))).json();
  $("detail").innerHTML = renderDetail(d);
}

async function startRun() {
  const templates = [...document.querySelectorAll(".checks input:checked")].map(c => c.value);
  const body = {templates, workers: +$("workers").value || 2, limit: +$("limit").value || 0,
                lesson_ids: $("lesson-ids").value};
  const res = await fetch("/api/run", {method: "POST", headers: {"Content-Type": "application/json"},
                                       body: JSON.stringify(body)});
  const data = await res.json();
  if (!res.ok) { alert(data.error || "فشل التشغيل"); return; }
  $("run-btn").disabled = true;
  pollRun();
}

async function pollRun() {
  const s = await (await fetch("/api/run/status")).json();
  $("run-log").textContent = s.tail.join("\n") || "لا يوجد تشغيل بعد.";
  $("run-log").scrollTop = $("run-log").scrollHeight;
  $("run-btn").disabled = s.running;
  if (s.running) setTimeout(pollRun, 2000);
  else { loadStats(); loadLessons(); }
}

loadStats(); loadLessons(); pollRun();
</script></body></html>"""

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
                lessons = filter_lessons(params.get("q", [""])[0])
                self._respond_json(lessons[:400])
            elif parsed.path == "/api/lesson":
                uuid = params.get("uuid", [""])[0]
                self._respond_json(lesson_detail(uuid) if uuid else {})
            elif parsed.path == "/api/run/status":
                self._respond_json(run_status())
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
