"""Structured stdout events shared by CLI runners and the dashboard."""
import json
import threading
from datetime import datetime, timezone

PREFIX = "ETGS_EVENT "
_lock = threading.Lock()


def emit(event, **fields):
    payload = {"event": event, "at": datetime.now(timezone.utc).isoformat(), **fields}
    with _lock:
        print(PREFIX + json.dumps(payload, ensure_ascii=False, default=str), flush=True)


def lesson_progress(lesson_id, template="knowledge_productions"):
    def report(stage, **fields):
        emit("stage", lesson_id=str(lesson_id), template=template, stage=stage, **fields)
    return report


def read_progress(lines):
    """Reduce events into lesson counts and currently active worker stages."""
    state = {"total": 0, "completed": 0, "successful": 0, "failed": 0,
             "skipped": 0, "active": {}, "finished": False,
             "final_status": None}
    for line in lines:
        if not line.startswith(PREFIX):
            continue
        try:
            item = json.loads(line[len(PREFIX):])
        except (ValueError, TypeError):
            continue
        event = item.get("event")
        key = str(item.get("lesson_id", ""))
        if event == "run_started":
            state.update(total=item["total"], completed=0, successful=0, failed=0,
                         skipped=0, active={}, finished=False, final_status=None)
        elif event == "discovery_started":
            state["active"][key] = item
        elif event == "discovery_completed":
            state["active"].pop(key, None)
        elif event in {"lesson_started", "stage"}:
            state["active"][key] = {**state["active"].get(key, {}), **item}
        elif event == "lesson_completed":
            state["active"].pop(key, None)
            state["completed"] += 1
            status = item.get("status")
            bucket = ("successful" if status in {"generated", "restored", "dry_run"} else
                      "skipped" if status in {"up_to_date", "skipped"} else "failed")
            state[bucket] += 1
        elif event == "run_finished":
            state["finished"] = True
            state["final_status"] = item.get("status")
    return state
