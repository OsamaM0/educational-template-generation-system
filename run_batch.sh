#!/usr/bin/env bash
# Fill-missing AI batch: builds the candidate lesson list, splits it into
# chunks and runs one questions_cycle.py worker per chunk in parallel.
#
# Usage:
#   bash run_batch.sh              # 16 workers (default)
#   WORKERS=8 bash run_batch.sh    # custom worker count
#
# Logs land in logs/chunkNN.log (also batch.log for this launcher).
set -u
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then PY=${PY:-.venv/bin/python}; else PY=${PY:-python3}; fi
WORKERS=${WORKERS:-16}
CHUNK_WORKERS=${CHUNK_WORKERS:-2}   # parallel lessons inside each chunk process
mkdir -p logs

echo "[batch] building candidate lesson ids (bulk scans)..."
$PY -u - <<'PYEOF' 2>/dev/null | grep -E '^[0-9]+$' | sort -n | uniq > /tmp/etgs_ids.txt
from clients.mongo_client import MongoDBClient
from clients.tahdiri_client import TahdiriQuestionsClient
from questions_cycle import build_lesson_documents, tahdiri_source_id

mongo = MongoDBClient()
tahdiri = TahdiriQuestionsClient()
mongo.connect()
tahdiri.connect()
for doc in build_lesson_documents(mongo, tahdiri):
    print(tahdiri_source_id(doc["idx"]))
tahdiri.disconnect()
mongo.disconnect()
PYEOF

total=$(wc -l < /tmp/etgs_ids.txt)
echo "[batch] $total unique lesson ids to process; splitting into $WORKERS chunks"
rm -f /tmp/etgs_chunk_* logs/chunk*.log
split -n l/$WORKERS -d /tmp/etgs_ids.txt /tmp/etgs_chunk_

for f in /tmp/etgs_chunk_*; do
    n=${f##*_}
    $PY -u questions_cycle.py --lesson-source-id $(cat "$f" | tr '\n' ' ') --workers "$CHUNK_WORKERS" > "logs/chunk$n.log" 2>&1 &
done
wait

echo "[batch] ALL_CHUNKS_DONE"
grep -h "Success Rate" logs/chunk*.log
