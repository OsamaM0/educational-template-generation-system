"""
Full AI Cycle driven by MongoDB `tahdiri` questions.

The *content* of each lesson is built from that lesson's questions in the
`tahdiri` database (grouped per lesson via `lessonSourceId`) instead of the
raw lesson text served by the document (PostgreSQL-backed) API.

For every lesson the cycle runs in enforced order:
    1. Summary  ->  2. Learning goals  ->  3. Worksheet
    ->  4. Goal-based questions  ->  5. Mind map

LLM provider: OpenRouter
- Math content:     xiaomi/mimo-v2.6-pro  (Xiaomi: MiMo-V2.6-Pro)
- Everything else:  z-ai/glm-5.3-flash    (Z.ai: GLM 5.3 Flash)

Results are stored in the MongoDB `ai` database (summaries / worksheets /
questions / mindmaps collections).

Usage examples:
    python questions_cycle.py --lesson-source-id 719
    python questions_cycle.py --limit 5 --templates summaries mindmaps
    python questions_cycle.py --limit 3 --dry-run
"""
import argparse
import os
import sys
from typing import List

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.mongo_client import DEFAULT_MONGODB_URI, MongoDBClient
from clients.tahdiri_client import TahdiriQuestionsClient
from config.settings import Settings
from generators.template_generator import TemplateGenerator
from processors.batch_processor import BatchProcessor

PREVIEW_LINES = 8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Full AI Cycle on lessons whose content is their tahdiri questions"
    )
    parser.add_argument("--lesson-source-id", type=int, nargs="*", default=None,
                        help="Specific lesson source id(s) (e.g. 719); default: all lessons")
    parser.add_argument("--limit", type=int, default=None,
                        help="Maximum number of lessons to process")
    parser.add_argument("--min-questions", type=int, default=1,
                        help="Skip lessons with fewer questions than this")
    parser.add_argument("--templates", nargs="*", default=["questions"],
                        choices=["summaries", "worksheets", "questions", "mindmaps"],
                        help="Templates to generate (questions auto-adds summaries + worksheets)")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip templates that already exist in the ai database")
    parser.add_argument("--workers", type=int, default=1,
                        help="Number of parallel workers (1 = sequential)")
    parser.add_argument("--mongo-url", default=DEFAULT_MONGODB_URI,
                        help="MongoDB connection string (tahdiri source + ai storage)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only show the questions-based content; no LLM calls, no storage")
    return parser.parse_args()


def print_dry_run_preview(documents: List[dict]):
    """Print the questions-as-content built for each lesson."""
    for doc in documents:
        print("\n" + "=" * 60)
        print(f"📗 {doc['filename']}  (uuid: {doc['uuid']})")
        print(f"   Source questions rendered as content: {len(doc['content'])} chars")
        print("-" * 60)
        for line in doc["content"].splitlines()[:PREVIEW_LINES]:
            print(f"   {line}")
        print("   ...")


def main() -> int:
    args = parse_args()

    tahdiri = TahdiriQuestionsClient(args.mongo_url)
    if not tahdiri.connect():
        return 1
    try:
        documents = tahdiri.get_lesson_documents(
            lesson_source_ids=args.lesson_source_id or None,
            limit=args.limit,
            min_questions=args.min_questions,
        )
    finally:
        tahdiri.disconnect()

    if not documents:
        print("❌ No lessons with questions found")
        return 1

    print(f"📚 Found {len(documents)} lesson(s) with questions")

    if args.dry_run:
        print_dry_run_preview(documents)
        return 0

    Settings.validate_config()

    mongo = MongoDBClient(args.mongo_url)
    if not mongo.connect():
        return 1
    try:
        processor = BatchProcessor(
            api_client=None,
            mongo_client=mongo,
            template_generator=TemplateGenerator(),
        )
        processor.process_documents(
            documents,
            template_types=args.templates,
            skip_existing=args.skip_existing,
            max_workers=args.workers,
        )
    finally:
        mongo.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
