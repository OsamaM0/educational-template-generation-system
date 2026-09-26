#!/usr/bin/env python3
"""Tiny read-only live dashboard for the fill-missing AI batch.

Serves real-time chunk logs + full counts on http://0.0.0.0:2006/ (stdlib only).
Usage: python3 live_dashboard.py --port 2006
"""
import argparse
import html
import re
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
START = time.time()


def collect() -> dict:
    stats = {"queued": 0, "done": 0, "mindmaps": 0, "failures": 0, "skips": 0}
    tail: list = []
    for log in sorted(LOG_DIR.glob("chunk*.log")):
        try:
            text = log.read_text(errors="replace")
        except OSError:
            continue
        stats["queued"] += sum(int(n) for n in re.findall(r"Found (\d+) AI lesson", text))
        stats["done"] += len(re.findall(r"Questions stored for document", text))
        stats["mindmaps"] += len(re.findall(r"Mind map stored for document", text))
        stats["failures"] += len(re.findall(r"❌ Failed to generate", text))
        stats["skips"] += len(re.findall(r"Skipping .* already exist", text))
        tail += [f"[{log.name}] {line}" for line in text.splitlines()[-12:]]
    try:
        batch_log = (LOG_DIR / "batch.log").read_text(errors="replace")
        tail = [f"[batch.log] {line}" for line in batch_log.splitlines()[-6:]] + tail
    except OSError:
        pass
    try:
        workers = int(subprocess.run(
            ["pgrep", "-fc", "questions_cycle[.]py"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip() or 0)
    except Exception:
        workers = -1

    remaining = max(stats["queued"] - stats["done"] - stats["skips"], 0)
    elapsed = time.time() - START
    eta = int((elapsed / stats["done"]) * remaining) if stats["done"] else None
    return {**stats, "workers": workers, "remaining": remaining, "eta": eta,
            "tail": tail[-60:], "elapsed": int(elapsed)}


def render() -> str:
    s = collect()
    eta = time.strftime("%H:%M:%S", time.gmtime(s["eta"])) if s["eta"] is not None else "—"
    pct = (100.0 * (s["done"] + s["skips"]) / s["queued"]) if s["queued"] else 0.0
    tail = "\n".join(html.escape(line) for line in s["tail"])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="5">
<title>ETGS batch — live</title>
<style>
 body{{background:#0d1117;color:#c9d1d9;font:14px/1.5 monospace;margin:0;padding:18px}}
 h1{{color:#58a6ff;font-size:18px}} .cards{{display:flex;gap:12px;flex-wrap:wrap;margin:12px 0}}
 .card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px 18px;min-width:110px}}
 .n{{font-size:24px;color:#58a6ff}} .l{{color:#8b949e;font-size:12px}}
 .bar{{background:#21262d;border-radius:6px;height:14px;margin:10px 0;overflow:hidden}}
 .fill{{background:#238636;height:100%}}
 pre{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px;overflow:auto;max-height:65vh}}
 .ok{{color:#3fb950}} .bad{{color:#f85149}}
</style></head><body>
<h1>🚀 ETGS fill-missing batch — live &nbsp;<span class="l">refresh 5s · uptime {time.strftime('%H:%M:%S', time.gmtime(s['elapsed']))}</span></h1>
<div class="cards">
 <div class="card"><div class="n">{s['queued']}</div><div class="l">queued</div></div>
 <div class="card"><div class="n ok">{s['done']}</div><div class="l">questions stored</div></div>
 <div class="card"><div class="n">{s['mindmaps']}</div><div class="l">mindmaps stored</div></div>
 <div class="card"><div class="n">{s['skips']}</div><div class="l">skipped (done)</div></div>
 <div class="card"><div class="n bad">{s['failures']}</div><div class="l">failures</div></div>
 <div class="card"><div class="n">{s['remaining']}</div><div class="l">remaining</div></div>
 <div class="card"><div class="n">{s['workers']}</div><div class="l">live workers</div></div>
 <div class="card"><div class="n">{eta}</div><div class="l">ETA</div></div>
</div>
<div class="bar"><div class="fill" style="width:{pct:.1f}%"></div></div>
<div class="l">{pct:.1f}% complete</div>
<pre>{tail}</pre>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = render().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live batch dashboard")
    parser.add_argument("--port", type=int, default=2006)
    args = parser.parse_args()
    print(f"📊 live dashboard on http://0.0.0.0:{args.port}/", flush=True)
    ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()