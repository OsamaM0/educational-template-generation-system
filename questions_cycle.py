"""
Full AI Cycle driven by MongoDB `tahdiri` questions.

The cycle per lesson (fill the MISSING AI templates; existing ones are kept):
    1. Pick the lesson (0 generated questions) from the AI database
    ->  2. File info (name) from `ien-v2.lessons`  (join key: lessonId)
    ->  3. Content source (first match wins):
          a. the lesson's existing AI summary (richer, more detailed data), or
          b. tahdiri questions + ien-v2 name (original method; join key: lessonId)
    ->  4. Generate only the missing templates (summary -> learning goals ->
       worksheet -> goal-based questions -> mind map -> knowledge production) and store them into
       the AI database; existing records are never overwritten

LLM provider: OpenRouter
- Math content:     xiaomi/mimo-v2.6-pro  (Xiaomi: MiMo-V2.6-Pro)
- Everything else:  z-ai/glm-5.3-flash    (Z.ai: GLM 5.3 Flash)

Results are stored in the MongoDB `ai` database (summaries / worksheets /
questions / mindmaps / knowledge_productions collections).

Usage examples:
    python questions_cycle.py --dry-run
    python questions_cycle.py --limit 5
    python questions_cycle.py --lesson-source-id 152225
    python questions_cycle.py --skip mindmaps
"""
import argparse
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.mongo_client import (
    AI_TEMPLATE_COLLECTIONS,
    DEFAULT_MONGODB_URI,
    MongoDBClient,
    short_idx,
)
from clients.tahdiri_client import TahdiriQuestionsClient, build_lesson_content
from config.settings import Settings
from generators.template_generator import TemplateGenerator
from processors.batch_processor import BatchProcessor
from utils.run_progress import emit

PREVIEW_LINES = 8
QUESTION_FETCH_CHUNK = 100  # lessons per bulk questions query


def tahdiri_source_id(document_idx: Any) -> Optional[int]:
    """Map an AI document idx to the shared lessonId (tahdiri `lessons.sourceId`)."""
    value = short_idx(document_idx)
    return int(value) if str(value).isdigit() else None


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Full AI Cycle on lessons whose content is their tahdiri questions"
    )
    parser.add_argument("--lesson-source-id", type=int, nargs="*", default=None,
                        help="Specific lesson id(s) (= AI document idx = ien-v2 lessonId); "
                             "default: all AI lessons with 0 questions")
    parser.add_argument("--limit", type=int, default=None,
                        help="Maximum number of lessons to process")
    parser.add_argument("--min-questions", type=int, default=1,
                        help="Skip lessons with fewer tahdiri questions than this")
    parser.add_argument("--templates", nargs="*",
                        default=["summaries", "worksheets", "questions", "mindmaps", "knowledge_productions"],
                        choices=["summaries", "worksheets", "questions", "mindmaps", "knowledge_productions"],
                        help="Templates to generate (questions auto-adds summaries + worksheets)")
    parser.add_argument("--skip", nargs="*", default=[],
                        choices=["summaries", "worksheets", "questions", "mindmaps", "knowledge_productions"],
                        help="Templates to skip entirely (e.g. --skip mindmaps worksheets)")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip templates that already exist in the ai database")
    parser.add_argument("--workers", type=int, default=1,
                        help="Number of parallel workers (1 = sequential)")
    parser.add_argument("--mongo-url", default=DEFAULT_MONGODB_URI,
                        help="MongoDB connection string (tahdiri source + ai storage)")
    parser.add_argument("--force-knowledge", action="store_true",
                        help="Regenerate current knowledge productions too")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only show the questions-based content; no LLM calls, no storage")
    args = parser.parse_args(argv)
    if args.workers < 1 or (args.limit is not None and args.limit < 1):
        parser.error("workers and limit must be positive")
    if not set(args.templates) - set(args.skip):
        parser.error("select at least one template that is not skipped")
    return args


def print_dry_run_preview(documents: List[dict]):
    """Print the content and template targets built for each lesson."""
    for doc in documents:
        print("\n" + "=" * 60)
        print(f"📗 {doc['filename']}  (uuid: {doc['uuid']})")
        print(f"   content source: {doc['content_source']} ({len(doc['content'])} chars)")
        print(f"   templates to process/check: {', '.join(doc['template_types'])}")
        print("-" * 60)
        for line in doc["content"].splitlines()[:PREVIEW_LINES]:
            print(f"   {line}")
        print("   ...")


def build_new_lesson_documents(
    mongo: MongoDBClient,
    tahdiri: TahdiriQuestionsClient,
    wanted: Optional[set],
    requested: set,
    skipped: set,
    min_questions: int,
    file_infos: Dict[int, Dict[str, Any]],
    uuid_sets: Dict[str, set],
    covered_uuids: set,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Documents for ien-v2 lessons without a complete AI record.

    Universe: ien-v2 lessonIds (the master list) that either have no AI
    record at all or only a partial synthetic one. Content source: lesson
    title + the lesson's tahdiri questions, joined via tahdiri
    `lessons.apiSourceId` == ien-v2 `lessonId`. Identity is synthesized
    (uuid `tahdiri-<lessonId>`) so re-runs upsert the same records; only the
    templates missing for that uuid are targeted, so interrupted runs resume
    cleanly. Lessons with no tahdiri questions are skipped (title alone is
    not enough content to generate from).
    """
    targets = [t for t in AI_TEMPLATE_COLLECTIONS if t in requested and t not in skipped]
    if not targets:
        return []

    generated_ids = mongo.get_generated_lesson_ids()
    all_uuids = set().union(*uuid_sets.values()) if uuid_sets else set()

    pending = []
    for lesson_id in sorted(file_infos, key=str):
        if wanted is not None and lesson_id not in wanted:
            continue
        doc_uuid = f"tahdiri-{lesson_id}"
        if doc_uuid in all_uuids:
            if doc_uuid in covered_uuids:
                continue  # fill-missing pass already handles this record
        elif str(lesson_id) in generated_ids:
            continue  # has an original-uuid record; the fill-missing pass owns it
        missing = [t for t in targets if doc_uuid not in uuid_sets.get(t, set())]
        if missing:
            pending.append((lesson_id, doc_uuid, missing))

    # Fetch questions lazily per chunk so limit-sized runs stay fast
    documents: List[Dict[str, Any]] = []
    for start in range(0, len(pending), QUESTION_FETCH_CHUNK):
        chunk = pending[start:start + QUESTION_FETCH_CHUNK]
        source_map = tahdiri.get_source_ids_by_api_ids([item[0] for item in chunk])
        source_ids = [sid for sids in source_map.values() for sid in sids]
        questions_by_source = tahdiri.get_questions_by_lessons(source_ids)
        for lesson_id, doc_uuid, missing in chunk:
            if limit is not None and len(documents) >= limit:
                return documents
            questions = []
            for source_id in source_map.get(str(lesson_id), []):
                questions.extend(questions_by_source.get(source_id, []))
            if len(questions) < min_questions:
                continue
            documents.append(_new_lesson_document(
                lesson_id, file_infos.get(lesson_id) or {}, questions, missing,
            ))
    return documents


def _new_lesson_document(
    lesson_id: Any,
    file_info: Dict[str, Any],
    questions: List[Dict[str, Any]],
    targets: List[str],
) -> Dict[str, Any]:
    """Shape one no-AI-record lesson as a generation document."""
    lesson_title = file_info.get("title") or f"Lesson {lesson_id}"
    return {
        "uuid": f"tahdiri-{lesson_id}",
        "idx": str(lesson_id),
        "custom_id": str(lesson_id),
        "filename": lesson_title,
        "content": build_lesson_content(
            {"title": lesson_title, "unit_title": file_info.get("extended_title")},
            questions,
        ),
        "template_types": targets,
        "content_source": "tahdiri-new",
    }


def summary_to_text(title: str, summary_payload: Optional[Dict[str, Any]]) -> str:
    """Render a stored AI summary as lesson content (the richer data source)."""
    payload = summary_payload or {}
    parts = [f"عنوان الدرس: {title}", ""]
    for key in ("opening", "summary", "ending"):
        text = str(payload.get(key) or "").strip()
        if text:
            parts.append(text)
            parts.append("")
    return "\n".join(parts).strip()


def build_lesson_documents(
    mongo: MongoDBClient,
    tahdiri: TahdiriQuestionsClient,
    lesson_source_ids: Optional[List[int]] = None,
    min_questions: int = 1,
    limit: Optional[int] = None,
    template_types: Optional[List[str]] = None,
    skip_templates: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Fill the missing AI templates of every AI lesson with 0 questions.

    Content source per lesson (first match wins):
      1. the lesson's existing AI summary (richer data), else
      2. tahdiri questions + ien-v2 name (original method).

    Only lessons listed in `ien-v2.lessons` are considered. Document identity
    (uuid/idx/custom_id) is kept from the AI database and `template_types`
    pins each run to the lesson's missing templates, so existing records are
    never overwritten. All AI/ien-v2 state is bulk-loaded up front to keep the
    remote round-trips to one query per collection.
    """
    wanted = set(lesson_source_ids) if lesson_source_ids else None
    requested = set(template_types) if template_types else set(AI_TEMPLATE_COLLECTIONS)
    skipped = set(skip_templates or ())
    if requested & {"questions", "knowledge_productions"}:
        requested.update({"summaries", "worksheets"} - skipped)
    if wanted is not None:
        return build_targeted_lesson_documents(
            mongo, tahdiri, wanted, requested, skipped, min_questions, limit)
    uuid_sets = mongo.get_template_uuid_sets()
    file_infos = mongo.get_all_lesson_file_info()
    candidates = mongo.find_documents_missing_templates(requested - skipped)
    summaries = mongo.get_stored_summaries([doc["uuid"] for doc in candidates])

    documents: List[Dict[str, Any]] = []
    for ai_doc in candidates:
        lesson_id = tahdiri_source_id(ai_doc.get("idx"))
        if lesson_id is None or (wanted is not None and lesson_id not in wanted):
            continue
        file_info = file_infos.get(lesson_id)
        if not file_info:
            file_info = {"title": ai_doc.get("filename")}
        missing = [t for t in AI_TEMPLATE_COLLECTIONS
                   if (ai_doc["uuid"] not in uuid_sets[t] or t == "knowledge_productions")
                   and t in requested and t not in skipped]
        if not missing:
            continue
        lesson_title = file_info.get("title") or ai_doc.get("filename")

        summary_payload = summaries.get(ai_doc["uuid"])
        if summary_payload:
            content = summary_to_text(lesson_title, summary_payload)
            targets = [t for t in missing if t != "summaries"]
            content_source = "ai-summary"
        else:
            questions = tahdiri.get_questions_for_api_lesson(lesson_id)
            if len(questions) < min_questions:
                continue
            content = build_lesson_content(
                {"title": lesson_title, "unit_title": file_info.get("extended_title")},
                questions,
            )
            targets = missing
            content_source = "tahdiri-questions"
        if not targets:
            continue

        documents.append({
            "uuid": ai_doc["uuid"],
            "idx": ai_doc["idx"],
            "custom_id": ai_doc["custom_id"],
            "filename": lesson_title,
            "content": content,
            "template_types": targets,
            "content_source": content_source,
        })
        if limit and len(documents) >= limit:
            break

    # Lessons with NO AI record at all: title + tahdiri questions = content
    remaining = max(limit - len(documents), 0) if limit else None
    if not limit or remaining:
        new_documents = build_new_lesson_documents(
            mongo, tahdiri,
            wanted=wanted, requested=requested, skipped=skipped,
            min_questions=min_questions, file_infos=file_infos,
            uuid_sets=uuid_sets, covered_uuids={d["uuid"] for d in documents},
            limit=remaining,
        )
        if new_documents:
            print(f"🆕 {len(new_documents)} lesson(s) with no AI record yet (title + tahdiri questions)")
        documents.extend(new_documents)
    return documents


def build_targeted_lesson_documents(mongo, tahdiri, lesson_ids, requested, skipped,
                                    min_questions, limit):
    """Look up explicit lesson IDs directly instead of scanning every AI record."""
    documents = []
    targets = [t for t in AI_TEMPLATE_COLLECTIONS if t in requested and t not in skipped]
    if not targets:
        return documents
    projection = {"document_uuid": 1, "document_idx": 1, "custom_id": 1, "filename": 1}
    for lesson_id in sorted(lesson_ids, key=str):
        query = {"document_idx": {"$in": [str(lesson_id), lesson_id]}}
        identities = {}
        present = {}
        for name in AI_TEMPLATE_COLLECTIONS:
            for row in mongo.storage_db[name].find(query, projection):
                uuid = row.get("document_uuid")
                if not uuid:
                    continue
                identity = identities.setdefault(uuid, {"uuid": uuid, "idx": row.get("document_idx"),
                                                     "custom_id": row.get("custom_id"),
                                                     "filename": row.get("filename")})
                for field, source in (("idx", "document_idx"), ("custom_id", "custom_id"),
                                      ("filename", "filename")):
                    identity[field] = identity[field] or row.get(source)
                present.setdefault(uuid, set()).add(name)

        file_info = mongo.get_lesson_file_info(lesson_id) or {}
        if not identities:
            # Match the all-lessons path: the ien-v2 lesson is the master list.
            if not file_info:
                continue
            questions = tahdiri.get_questions_for_api_lesson(lesson_id)
            if len(questions) >= min_questions:
                documents.append(_new_lesson_document(lesson_id, file_info, questions, targets))
            if limit and len(documents) >= limit:
                break
            continue

        for uuid, identity in identities.items():
            known = present[uuid]
            for name in targets:
                if name not in known and mongo.storage_db[name].find_one(
                        {"document_uuid": uuid}, {"_id": 1}):
                    known.add(name)
            missing = [t for t in targets if t == "knowledge_productions" or t not in known]
            if not missing:
                continue
            title = file_info.get("title") or identity.get("filename")
            summary = mongo.storage_db["summaries"].find_one(
                {"document_uuid": uuid}, {"summary": 1}) if "summaries" in known else None
            if summary and summary.get("summary"):
                content = summary_to_text(title, summary["summary"])
                missing = [t for t in missing if t != "summaries"]
                source = "ai-summary"
            else:
                questions = tahdiri.get_questions_for_api_lesson(lesson_id)
                if len(questions) < min_questions:
                    continue
                content = build_lesson_content(
                    {"title": title, "unit_title": file_info.get("extended_title")}, questions)
                source = "tahdiri-questions"
            if missing:
                documents.append({**identity, "filename": title, "content": content,
                                  "template_types": missing, "content_source": source})
            if limit and len(documents) >= limit:
                return documents
    return documents


def main(argv=None) -> int:
    args = parse_args(argv)
    selected = set(args.templates) - set(args.skip)
    if selected == {"knowledge_productions"}:
        # Backfill complete lessons too, without requiring Tahdiri or ien-v2.
        from knowledge_production import main as knowledge_main
        command = ["--mongo-url", args.mongo_url, "--workers", str(args.workers)]
        if args.lesson_source_id:
            command += ["--lesson-id", *map(str, args.lesson_source_id)]
        else:
            command += ["--all"]
        if args.limit:
            command += ["--limit", str(args.limit)]
        if args.force_knowledge:
            command += ["--force"]
        if args.dry_run:
            command += ["--dry-run"]
        return knowledge_main(command)

    mongo = MongoDBClient(args.mongo_url)
    tahdiri = TahdiriQuestionsClient(args.mongo_url)
    if not (mongo.connect() and tahdiri.connect()):
        return 1

    try:
        # Steps 1-4: AI lessons with 0 questions -> ien-v2 name + tahdiri questions = content
        emit("discovery_started", lesson_id="selection", template="cycle",
             stage="select_lessons", requested_ids=args.lesson_source_id or [])
        documents = build_lesson_documents(
            mongo,
            tahdiri,
            lesson_source_ids=args.lesson_source_id or None,
            min_questions=args.min_questions,
            limit=args.limit,
            template_types=args.templates,
            skip_templates=args.skip,
        )
        emit("discovery_completed", lesson_id="selection", template="cycle",
             stage="select_lessons", total=len(documents))
        if not documents:
            emit("run_started", total=0)
            emit("run_finished", status="empty")
            print("❌ No lessons need the selected templates or have usable source content")
            return 1

        print(f"📚 Found {len(documents)} AI lesson(s) to update")

        if args.dry_run:
            emit("run_started", total=len(documents), templates=args.templates)
            print_dry_run_preview(documents)
            for doc in documents:
                emit("lesson_completed", lesson_id=doc["uuid"], status="dry_run")
            emit("run_finished", status="dry_run")
            return 0

        Settings.validate_config()

        processor = BatchProcessor(
            api_client=None,
            mongo_client=mongo,
            template_generator=TemplateGenerator(),
            generator_factory=TemplateGenerator,
            force_knowledge=args.force_knowledge,
        )
        stats = processor.process_documents(
            documents,
            template_types=args.templates,
            skip_existing=args.skip_existing,
            max_workers=args.workers,
        )
    finally:
        tahdiri.disconnect()
        mongo.disconnect()
    return int(bool(stats.failed_documents or sum(stats.get_summary()["template_failures"].values())))


if __name__ == "__main__":
    sys.exit(main())
