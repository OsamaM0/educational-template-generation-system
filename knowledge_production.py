#!/usr/bin/env python3
"""Create knowledge productions from existing MongoDB lesson records only.

    python knowledge_production.py --all --dry-run
    python knowledge_production.py --lesson-id 445
    python knowledge_production.py --all --workers 4

Reads summaries + worksheet goals + optional questions, then validates and
upserts one record per lesson in ai.knowledge_productions. No source templates
are generated or changed. The existing collection needs no schema maintenance.
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

# Resolve .env beside this command even when launched from another directory.
load_dotenv(Path(__file__).resolve().parent / ".env")

from kp.config import Settings
from kp.content import ID_TYPES, open_content
from kp.llm import OpenRouterLLM, ReplayLLM, StubLLM, Usage
from kp.pipeline import generate_lesson
from kp.store import candidates, ensure_collection
from kp.pending import restore_pending
from utils.run_progress import emit, lesson_progress


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--lesson-id", "--lesson-source-id", nargs="+",
                        help="lesson document idx(s); use --id-type for UUID or custom_id")
    source.add_argument("--from-file", type=Path, help="UTF-8 file, one lesson id per line")
    source.add_argument("--all", action="store_true", help="all lessons with an existing summary")
    source.add_argument("--resume-pending", type=Path,
                        help="import queued validated records from a file or directory after MongoDB recovers")
    parser.add_argument("--id-type", choices=ID_TYPES, default="idx")
    parser.add_argument("--mongo-url", help="override KP_MONGO_URI / MONGODB_URI")
    parser.add_argument("--database", help="override KP_MONGO_DB (default: ai)")
    parser.add_argument("--collection", help="destination collection (default: knowledge_productions)")
    parser.add_argument("--workers", type=positive_int, default=1)
    parser.add_argument("--limit", type=positive_int, help="process at most N lessons")
    parser.add_argument("--goals", help="only these goal ids, comma-separated")
    parser.add_argument("--force", action="store_true", help="regenerate up-to-date productions too")
    parser.add_argument("--dry-run", action="store_true", help="read-only plan; no LLM calls or DB writes")
    parser.add_argument("--local-out", type=Path, help="save validated JSON here instead of MongoDB")
    parser.add_argument("--report", type=Path, help="run report path (default: logs/knowledge-production-*.json)")
    parser.add_argument("--journal", type=Path,
                        help="append one result and its token usage per lesson (default: report path with .jsonl)")
    parser.add_argument("--llm", choices=("openrouter", "stub", "replay"), default="openrouter")
    parser.add_argument("--replay-file", type=Path, help="authored knowledge-production JSON for replay")
    parser.add_argument("--setup-collection", action="store_true",
                        help="explicitly create/update the destination validator and indexes")
    args = parser.parse_args(argv)
    if args.llm == "replay" and not args.replay_file:
        parser.error("--llm replay requires --replay-file")
    if args.llm == "stub" and not (args.local_out or args.dry_run):
        parser.error("--llm stub requires --local-out or --dry-run to keep placeholder text out of MongoDB")
    if args.setup_collection and (args.dry_run or args.local_out):
        parser.error("--setup-collection cannot be combined with --dry-run or --local-out")
    if args.goals is not None and not any(g.strip() for g in args.goals.split(",")):
        parser.error("--goals must contain at least one goal id")
    return args


def run(args, db, settings):
    """Shared runner; db injection permits offline integration tests."""
    if args.report is None:
        args.report = Path("logs") / f"knowledge-production-{time.strftime('%Y%m%d-%H%M%S')}.json"
    if args.journal is None:
        args.journal = args.report.with_suffix(".jsonl")
    args.journal.parent.mkdir(parents=True, exist_ok=True)
    if args.setup_collection:
        print(f"collection {settings.col_knowledge}: {ensure_collection(db, settings.col_knowledge)}")
    if args.resume_pending:
        source = args.resume_pending
        paths = sorted(source.glob('*.json')) if source.is_dir() else [source]
        if args.limit:
            paths = paths[:args.limit]
        if not paths or any(not path.is_file() for path in paths):
            print(f'No pending records at {source}')
            return 1
        emit('run_started', total=len(paths), templates=['knowledge_productions'])
        results = []
        for path in paths:
            emit('lesson_started', lesson_id=path.name)
            try:
                record = restore_pending(path, db, settings, dry_run=args.dry_run)
                result = {'lesson_id':record['document_idx'],
                          'document_uuid':record['document_uuid'],
                          'status':'dry_run' if args.dry_run else 'restored',
                          'products':len(record['products'])}
            except Exception as exc:
                result = {'lesson_id':path.name, 'status':'error',
                          'reason':f'{type(exc).__name__}: {exc}'}
            results.append(result)
            with args.journal.open("a", encoding="utf-8") as journal:
                journal.write(json.dumps({"finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                          "result": result, "usage": Usage().as_dict(settings)},
                                         ensure_ascii=False, default=str) + "\n")
            emit('lesson_completed', lesson_id=result['lesson_id'], status=result['status'],
                 products=result.get('products', 0), reason=result.get('reason'))
            print(f"  {result['status']:12} {result['lesson_id']}: {result.get('reason') or str(result.get('products')) + ' products'}")
        return finish_report(args, settings, results, Usage(), success={'restored', 'dry_run'})
    if args.all:
        lessons = candidates(db, settings.col_summaries, args.limit)
    else:
        raw = args.lesson_id or args.from_file.read_text(encoding="utf-8").splitlines()
        lessons = list(dict.fromkeys((str(value).strip(), args.id_type)
                                     for value in raw if str(value).strip()))
        if args.limit:
            lessons = lessons[:args.limit]
    if not lessons:
        emit('run_started', total=0)
        emit('run_finished', status='no_content')
        print("No matching lessons. Existing summary content and worksheet goals are required.")
        return 1
    content = open_content(settings, db)
    replay = json.loads(args.replay_file.read_text(encoding="utf-8")) if args.llm == "replay" else None
    goals = {g.strip() for g in args.goals.split(",") if g.strip()} if args.goals else None

    def one(lesson):
        lesson_id, id_type = lesson
        emit('lesson_started', lesson_id=lesson_id)
        started, llm = time.monotonic(), None
        try:
            if args.dry_run or args.llm == "stub":
                llm = StubLLM()
            elif args.llm == "replay":
                llm = ReplayLLM(replay)
            else:
                llm = OpenRouterLLM(settings)
            progress = {} if getattr(llm, 'legacy_archetypes', False) else {'progress': lesson_progress(lesson_id)}
            result = generate_lesson(lesson_id, id_type, content_src=content, db=db,
                                     llm=llm, s=settings, force=args.force, only_goals=goals,
                                     dry_run=args.dry_run, store_record=args.local_out is None, **progress)
            record = result.pop("_record", None)
            if record is not None:
                args.local_out.mkdir(parents=True, exist_ok=True)
                # UUID-based names avoid collisions for lessons sharing an idx.
                import hashlib
                suffix = hashlib.sha256(record["document_uuid"].encode()).hexdigest()[:12]
                path = args.local_out / f"lesson-{suffix}-knowledge-production.json"
                path.write_text(json.dumps(record, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
                result["local_record"] = str(path)
        except Exception as exc:
            result = {"lesson_id": lesson_id, "status": "error",
                      "reason": f"{type(exc).__name__}: {exc}"}
        result["seconds"] = round(time.monotonic() - started, 1)
        return result, llm.usage if llm else Usage()

    results, total = [], Usage()
    emit('run_started', total=len(lessons), templates=['knowledge_productions'])
    print(f"{len(lessons)} lesson(s) | destination={settings.mongo_db}.{settings.col_knowledge}"
          f" | workers={args.workers}" + (" | DRY RUN" if args.dry_run else ""))
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for future in as_completed([pool.submit(one, lesson) for lesson in lessons]):
            result, usage = future.result()
            results.append(result)
            total.merge(usage)
            with args.journal.open("a", encoding="utf-8") as journal:
                journal.write(json.dumps({"finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                          "result": result, "usage": usage.as_dict(settings)},
                                         ensure_ascii=False, default=str) + "\n")
            emit('lesson_completed', lesson_id=result['lesson_id'], status=result['status'],
                 products=result.get('products', 0), reason=result.get('reason'),
                 failed_goals=result.get('failed_goals', []))
            details = result.get("reason") or f"{result.get('products', 0)} products"
            if result["status"] == "dry_run":
                details = f"up to {result['plan']['calls']} model calls; {len(result['plan']['goals'])} goals"
            if result.get("failed_goals"):
                details += "; failed goals: " + ", ".join(g["goal_id"] for g in result["failed_goals"])
            print(f"  {result['status']:12} {result.get('document_idx') or result['lesson_id']}: {details}")
    return finish_report(args, settings, results, total,
                         success={'generated', 'up_to_date', 'dry_run'})


def finish_report(args, settings, results, total, success):
    counts = {}
    for result in results:
        counts[result["status"]] = counts.get(result["status"], 0) + 1
    report = {"finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "llm": args.llm,
              "dry_run": args.dry_run, "database": settings.mongo_db,
              "collection": settings.col_knowledge, "counts": counts,
              "usage": total.as_dict(settings), "journal": str(args.journal), "results": results}
    path = args.report
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"{counts} | {total.calls} model calls | "
          f"{report['usage']['total_tokens']} tokens | "
          f"estimated cost ${report['usage']['estimated_cost_usd']:.6f} USD | report: {path}")
    emit('run_finished', counts=counts, report=str(path))
    # Missing prerequisites and partial output need attention, including in backfills.
    return int(any(result['status'] not in success for result in results))


def main(argv=None):
    args = parse_args(argv)
    settings = Settings()
    settings.mongo_uri = args.mongo_url or settings.mongo_uri
    settings.mongo_db = args.database or settings.mongo_db
    settings.col_knowledge = args.collection or settings.col_knowledge
    if not settings.mongo_uri:
        print("Set MONGODB_URI or KP_MONGO_URI in .env, or pass --mongo-url.", file=sys.stderr)
        return 1
    sources = {settings.col_summaries, settings.col_worksheets, settings.col_questions, "mindmaps"}
    if settings.col_knowledge in sources:
        print("The destination collection must differ from the source collections.", file=sys.stderr)
        return 1
    from pymongo import MongoClient
    try:
        with MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=10000) as client:
            return run(args, client[settings.mongo_db], settings)
    except Exception as exc:
        print(f"Knowledge-production run failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
