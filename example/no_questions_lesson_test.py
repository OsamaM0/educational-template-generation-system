"""
Test run: the Full AI Cycle for a lesson that has NO generated questions yet.

The cycle under test (lesson content = tahdiri questions + the ien-v2 lesson name):
    1. Pick a lesson with 0 questions from the AI database
    2. Read its file information (name) from `ien-v2.lessons` (join key: lessonId)
    3. Search for that lesson's questions in the MongoDB `tahdiri` question bank
    4. tahdiri questions + the ien-v2 name = content (stands in for the
       PostgreSQL document content) and drive the full AI pipeline:
       summary -> learning goals -> worksheet -> goal-based questions -> mind map
    5. Store Questions / Mind maps / Worksheets / Summaries in the AI database

The report shows the lesson BEFORE (AI DB state + tahdiri source), every stage of
the life cycle, and the lesson AFTER (AI DB state).

Usage:
    python example/no_questions_lesson_test.py                  # offline rehearsal (fake models, no writes)
    python example/no_questions_lesson_test.py --live           # real OpenRouter + real writes to the ai DB
    python example/no_questions_lesson_test.py --document-idx 38071
"""
import argparse
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

# Load .env first, then fall back to a dummy key for the offline rehearsal
load_dotenv()
os.environ.setdefault("OPENROUTER_API_KEY", "offline-demo-key")

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.mongo_client import MongoDBClient, short_idx
from clients.tahdiri_client import (
    TahdiriQuestionsClient,
    build_lesson_content,
    format_question,
)
from config.settings import Settings
from generators.template_generator import TemplateGenerator
from questions_cycle_demo import install_fake_models, print_call_log

# Same question mix as BatchProcessor._process_single_document
QUESTION_COUNTS = {"multiple_choice": 2, "short_answer": 2, "complete": 2, "true_false": 2}
QUESTION_LIST_KEYS = ("multiple_choice", "short_answer", "complete", "true_false")
PREVIEW_LINES = 6


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test the Full AI Cycle on one lesson with 0 questions in the ai database"
    )
    parser.add_argument("--document-idx", type=int, default=None,
                        help="AI document idx (= tahdiri lesson sourceId) to test; default: first candidate")
    parser.add_argument("--live", action="store_true",
                        help="Real OpenRouter calls and real writes to the ai database")
    return parser.parse_args()


def tahdiri_source_id(document_idx: Any) -> Optional[int]:
    """Map an AI document idx to a tahdiri `lessons.sourceId`."""
    value = short_idx(document_idx)
    return int(value) if str(value).isdigit() else None


def pick_lesson(
    mongo: MongoDBClient,
    tahdiri: TahdiriQuestionsClient,
    document_idx: Optional[int] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[List[Dict[str, Any]]]]:
    """Steps 1-3: AI lesson with 0 questions -> ien-v2 file info -> tahdiri questions.

    Only lessons present in `ien-v2.lessons` are considered: that collection is
    the master list of lessons that belong in the AI database.
    """
    candidates = mongo.find_documents_missing_questions()
    if document_idx is not None:
        candidates = [d for d in candidates if tahdiri_source_id(d.get("idx")) == document_idx]

    for ai_doc in candidates:
        lesson_id = tahdiri_source_id(ai_doc.get("idx"))
        if lesson_id is None:
            continue
        file_info = mongo.get_lesson_file_info(lesson_id)
        if not file_info:
            continue
        questions = tahdiri.get_questions_by_lesson(lesson_id)
        if questions:
            return ai_doc, file_info, questions
    return None, None, None


def build_content(file_info: Dict[str, Any], questions: List[Dict[str, Any]]) -> str:
    """Step 4: content = tahdiri questions + the lesson's name from ien-v2."""
    lesson = {
        "title": file_info.get("title"),
        "unit_title": file_info.get("extended_title"),  # curriculum path as المنهج
    }
    return build_lesson_content(lesson, questions)


def count_generated_questions(stored_record: Optional[Dict[str, Any]]) -> int:
    """Number of generated question items inside a stored `questions` record."""
    payload = (stored_record or {}).get("questions") or {}
    return sum(len(payload.get(key) or []) for key in QUESTION_LIST_KEYS)


def print_ai_state(label: str, status: Dict[str, int], generated_questions: int) -> None:
    """Print one BEFORE/AFTER snapshot of the lesson in the AI database."""
    print(f"\n📊 AI DATABASE — {label}")
    print(f"   summaries: {status.get('summaries', 0)}  |  worksheets: {status.get('worksheets', 0)}  |  "
          f"questions-records: {status.get('questions', 0)}  |  mindmaps: {status.get('mindmaps', 0)}")
    print(f"   generated questions: {generated_questions}")


def print_before(
    mongo: MongoDBClient,
    ai_doc: Dict[str, Any],
    file_info: Dict[str, Any],
    questions: List[Dict[str, Any]],
) -> None:
    """Show the lesson BEFORE: its AI DB state and its ien-v2 / tahdiri source."""
    print("=" * 70)
    print("🔍 BEFORE — picked because it has 0 questions in the AI database")
    print("=" * 70)
    print(f"📗 AI lesson: {ai_doc.get('filename')}  (uuid: {ai_doc.get('uuid')}, idx: {ai_doc.get('idx')})")
    status = mongo.get_template_status(ai_doc["uuid"])
    print_ai_state("BEFORE", status,
                   count_generated_questions(mongo.get_stored_record(ai_doc["uuid"], "questions")))

    print(f"\n📄 ien-v2 lesson file (lessonId {file_info['lesson_id']}):")
    print(f"   name: {file_info.get('title')}")
    if file_info.get("extended_title"):
        print(f"   path: {file_info['extended_title']}")
    print(f"   tahdiri questions found: {len(questions)}")
    for i, question in enumerate(questions[:2], 1):
        preview = format_question(i, question)
        print("\n".join(f"   {line}" for line in preview.splitlines()))
    if len(questions) > 2:
        print(f"   ... {len(questions) - 2} more")


def report_store(write: bool, stored: Optional[bool], label: str) -> None:
    """Print whether a template record really landed in the ai DB."""
    if not write:
        print(f"   💾 {label}: offline rehearsal — not written")
    elif stored:
        print(f"   💾 {label}: stored in ai DB")
    else:
        print(f"   ⚠️ {label}: NOT stored")


def refined_goals(worksheet: Dict[str, Any]) -> List[str]:
    """Goals refined by the worksheet (structured first, then flat)."""
    structured = worksheet.get("structured_goals") or []
    texts = [g.get("text") for g in structured
             if isinstance(g, dict) and str(g.get("text", "")).strip()]
    if texts:
        return texts
    flat = worksheet.get("goals")
    if isinstance(flat, list):
        return [str(x) for x in flat if str(x).strip()]
    return []


def run_full_cycle(
    generator: TemplateGenerator,
    mongo: MongoDBClient,
    document: Dict[str, Any],
    write: bool,
) -> Dict[str, Any]:
    """Steps 3-4: content -> summary -> goals -> worksheet -> questions -> mind map -> ai DB."""
    content = document["content"]

    print("\n" + "=" * 70)
    print("🔄 FULL LIFE CYCLE")
    print("=" * 70)

    print("\n── STAGE 0: content = tahdiri questions + ien-v2 lesson name ──")
    print(f"   {len(content)} chars of questions-as-content")
    for line in content.splitlines()[:PREVIEW_LINES]:
        print(f"   {line}")
    print("   ...")

    print("\n── STAGE 1: content analysis + model routing ──")
    analysis = generator.get_content_analysis(content)
    print(f"   subject_area: {analysis['subject_area']}, "
          f"is_mathematical: {analysis['is_mathematical']}, "
          f"language: {analysis['language']}")
    print(f"   ➜ routed to: {generator._select_model_name(analysis)}")

    print("\n── STAGE 2: summary ──")
    summary = generator.generate_summary(content)
    print(f"   opening: {str(summary.get('opening', ''))[:80]}...")
    report_store(write, mongo.store_summary(document, summary) if write else None, "summaries")

    print("\n── STAGE 3: learning goals ──")
    goals = mongo.get_goals_by_custom_id(document["custom_id"]) if document.get("custom_id") else []
    if goals:
        print(f"   📋 {len(goals)} goals from the ien database")
    else:
        goals = generator.content_processor.generate_learning_goals(content, count=5)
        print(f"   🎯 {len(goals)} AI-generated goals")
    for i, goal in enumerate(goals, 1):
        print(f"   {i}. {goal}")

    print("\n── STAGE 4: worksheet (refines goals) ──")
    worksheet = generator.generate_worksheet(content, goals)
    refined = refined_goals(worksheet)
    if refined:
        goals = refined
        print(f"   goals refined by worksheet: {len(goals)}")
    print(f"   applications: {len(worksheet.get('applications', []))}, "
          f"vocabulary: {len(worksheet.get('vocabulary', []))}, "
          f"teacher_guidelines: {len(worksheet.get('teacher_guidelines', []))}")
    report_store(write, mongo.store_worksheet(document, goals, worksheet) if write else None, "worksheets")

    print("\n── STAGE 5: goal-based questions ──")
    questions_result = generator.generate_goal_based_questions(
        content=content,
        goals=goals,
        question_counts=QUESTION_COUNTS,
        difficulty_levels=[1, 2],
    )
    goal_meta = questions_result.get("_goal_based_metadata", {})
    print(f"   scenario: {goal_meta.get('scenario', '?')}, "
          f"goals: {goal_meta.get('total_goals', 0)}, "
          f"questions: {goal_meta.get('total_questions', 0)}")
    sample = (questions_result.get("multiple_choice") or [{}])[0]
    print(f"   sample MCQ: {str(sample.get('question', ''))[:80]}")
    report_store(write, mongo.store_questions(document, goals, questions_result) if write else None, "questions")

    print("\n── STAGE 6: mind map ──")
    mindmap = generator.generate_mindmap(content)
    nodes = (mindmap or {}).get("nodeDataArray", [])
    root = next((n for n in nodes if n.get("parent") is None), {})
    print(f"   nodes: {len(nodes)}, root: {root.get('text', '?')}")
    report_store(write, mongo.store_mindmap(document, mindmap) if write else None, "mindmaps")

    return {"goals": goals, "questions": questions_result}


def print_after(
    mongo: MongoDBClient,
    document: Dict[str, Any],
    generated: Dict[str, Any],
    live: bool,
) -> None:
    """Show the lesson AFTER: its AI DB state (real with --live, simulated offline)."""
    print("\n" + "=" * 70)
    if live:
        print("🔍 AFTER — lesson state in the AI database")
        status = mongo.get_template_status(document["uuid"])
        generated_count = count_generated_questions(mongo.get_stored_record(document["uuid"], "questions"))
    else:
        print("🔍 AFTER (simulated — offline rehearsal, nothing written)")
        status = {"summaries": 1, "worksheets": 1, "questions": 1, "mindmaps": 1}
        generated_count = count_generated_questions({"questions": generated["questions"]})
    print("=" * 70)
    print(f"📗 AI lesson: {document['filename']}  (uuid: {document['uuid']}, idx: {document['idx']})")
    print_ai_state("AFTER", status, generated_count)

    sample = (generated["questions"].get("multiple_choice") or [{}])[0]
    print(f"\n   ✍️ first generated MCQ: {str(sample.get('question', ''))[:100]}")
    if sample.get("choices"):
        print(f"      choices: {sample['choices']}")


def main() -> int:
    args = parse_args()

    if args.live:
        if Settings.OPENROUTER_API_KEY == "offline-demo-key":
            print("❌ --live requires OPENROUTER_API_KEY in the environment or .env")
            return 1
    else:
        print("🧪 Offline rehearsal: deterministic fake models, nothing is written to the ai DB "
              "(use --live for real OpenRouter calls + real writes)")
        install_fake_models()

    mongo = MongoDBClient()
    tahdiri = TahdiriQuestionsClient()
    if not (mongo.connect() and tahdiri.connect()):
        return 1

    try:
        # Steps 1-3: lesson with 0 AI questions -> ien-v2 file info -> tahdiri questions
        ai_doc, file_info, questions = pick_lesson(mongo, tahdiri, args.document_idx)
        if not ai_doc:
            print("❌ No AI lesson with 0 questions (with ien-v2 info + tahdiri questions) found")
            return 1

        print_before(mongo, ai_doc, file_info, questions)

        # Step 4: tahdiri questions + ien-v2 name = content (replaces the PostgreSQL content)
        lesson_title = file_info.get("title") or ai_doc.get("filename")
        document = {
            "uuid": ai_doc["uuid"],
            "idx": ai_doc["idx"],
            "custom_id": ai_doc["custom_id"],
            "filename": lesson_title,
            "content": build_content({**file_info, "title": lesson_title}, questions),
        }

        generated = run_full_cycle(TemplateGenerator(), mongo, document, write=args.live)
        print_after(mongo, document, generated, args.live)
    finally:
        tahdiri.disconnect()
        mongo.disconnect()

    print_call_log()
    print("\n✅ Test finished: AI lesson with 0 questions -> ien-v2 name + tahdiri questions -> "
          "summary -> goals -> worksheet -> goal-based questions -> mind map -> ai DB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
