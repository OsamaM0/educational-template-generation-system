"""
Workflow demo/test: MongoDB `tahdiri` questions -> content -> Full AI Cycle.

Stages exercised end to end:
    MongoDB questions (per lesson)
        -> questions-as-content builder
        -> AI content analysis + model routing
        -> summary -> learning goals -> worksheet
        -> goal-based questions -> mind map

LLM provider: OpenRouter
- Math content:     xiaomi/mimo-v2.6-pro  (Xiaomi: MiMo-V2.6-Pro)
- Everything else:  z-ai/glm-5.3-flash    (Z.ai: GLM 5.3 Flash)

By default the demo runs offline with deterministic fake models (still reading
real lessons/questions from Mongo), so the full pipeline is testable without an
API key. Pass --live to make real OpenRouter calls (requires OPENROUTER_API_KEY).

Usage:
    python example/questions_cycle_demo.py               # offline, 2 lessons
    python example/questions_cycle_demo.py --live        # real OpenRouter calls
    python example/questions_cycle_demo.py --lesson-source-id 719
"""
import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List

from dotenv import load_dotenv

# Load .env first, then fall back to a dummy key for the offline demo
load_dotenv()
os.environ.setdefault("OPENROUTER_API_KEY", "offline-demo-key")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from clients.tahdiri_client import TahdiriQuestionsClient, build_lesson_content
from config.settings import Settings
from generators.template_generator import TemplateGenerator

DEMO_QUESTION_COUNTS = {"multiple_choice": 1, "short_answer": 1, "complete": 1, "true_false": 1}
PREVIEW_CHARS = 600


# --------------------------------------------------------------------------
# Deterministic fake models (offline demo only)
# --------------------------------------------------------------------------
CALL_LOG: List[Dict[str, str]] = []


def _extract_title(prompt_text: str) -> str:
    # Content is whitespace-normalized inside prompts, so stop at the next section
    match = re.search(r"عنوان الدرس: (.+?)(?:\s+المنهج:|\s+أسئلة الدرس|$)", prompt_text)
    return match.group(1).strip() if match else "الدرس"


def _detect_prompt_kind(prompt_text: str) -> str:
    """Classify which pipeline stage produced the prompt (marker-based)."""
    if "estimated_reading_time" in prompt_text:
        return "analysis"
    if "goal1" in prompt_text:
        return "goals"
    if "teacher_guidelines" in prompt_text:
        return "worksheet"
    if "answer_key" in prompt_text:
        return "questions"
    if "nodeDataArray" in prompt_text or "go.TreeModel" in prompt_text:
        return "mindmap"
    if any(marker in prompt_text for marker in ("افتتاحية", "خلاصة", "خاتمة", "ملخص")):
        return "summary"
    return "mindmap-planning"


def _is_math_content(prompt_text: str) -> bool:
    return "$" in prompt_text or "الرياضيات" in prompt_text


def _craft_response(kind: str, prompt_text: str) -> str:
    """Build a deterministic, schema-valid response for each pipeline stage."""
    title = _extract_title(prompt_text)
    is_math = _is_math_content(prompt_text)
    goals = [
        f"يشرح الطالب المفاهيم الأساسية في {title}",
        f"يطبق الطالب مهارات {title} في تمارين متنوعة",
        f"يحلل الطالب الأمثلة المرتبطة بـ {title}",
    ]

    if kind == "analysis":
        return json.dumps({
            "language": "arabic",
            "word_count": len(prompt_text.split()),
            "character_count": len(prompt_text),
            "estimated_reading_time": 5,
            "complexity_level": "medium",
            "key_topics": [title, "مفاهيم الدرس", "تطبيقات"],
            "is_mathematical": is_math,
            "math_concepts": ["القيمة المنزلية", "الكتابة اللفظية"] if is_math else [],
            "has_equations": is_math,
            "has_numbers": is_math,
            "subject_area": "mathematics" if is_math else "language",
        }, ensure_ascii=False)

    if kind == "goals":
        return json.dumps({"goals": goals}, ensure_ascii=False)

    if kind == "worksheet":
        return json.dumps({
            "goals": goals,
            "applications": [f"ورقة عمل تطبيقية حول {title}", "نشاط جماعي قصير"],
            "vocabulary": [{"term": title, "definition": "مفتاح مفاهيم الدرس"}],
            "teacher_guidelines": ["التركيز على الأمثلة التوضيحية", "تشجيع المشاركة الصفية"],
            "structured_goals": [
                {"id": f"goal_{i + 1}", "text": g, "priority": 1,
                 "activities": ["نشاط صفّي"], "assessment_methods": ["سؤال شفهي"]}
                for i, g in enumerate(goals)
            ],
        }, ensure_ascii=False)

    if kind == "questions":
        return json.dumps({
            "multiple_choice": [{
                "question": f"أي مما يلي يعبّر بشكل أفضل عن {title}؟",
                "choices": ["الخيار الأول", "الخيار الثاني", "الخيار الثالث", "الخيار الرابع"],
                "answer_key": 0, "difficulty": 1,
                "target_goal": goals[0], "goal_id": "goal_1",
            }],
            "short_answer": [{
                "question": f"اكتب جملة قصيرة تلخّص فيها {title}.",
                "answer": f"{title} محور الدرس الأساسي.", "difficulty": 1,
                "target_goal": goals[1], "goal_id": "goal_2",
            }],
            "complete": [{
                "question": f"يتعلقدرس {title} بمهارة ______ الأساسية.",
                "answer": "التطبيق", "difficulty": 1,
                "target_goal": goals[1], "goal_id": "goal_2",
            }],
            "true_false": [{
                "question": f"يدرس {title} مهارات تطبيقية متنوعة.",
                "choices": ["صح", "خطأ"], "answer_key": 0, "difficulty": 1,
                "target_goal": goals[2], "goal_id": "goal_3",
            }],
            "learning_goals": [], "goal_question_mapping": [], "questions_by_goal": {},
        }, ensure_ascii=False)

    if kind == "mindmap":
        return json.dumps({
            "class": "go.TreeModel",
            "nodeDataArray": [
                {"key": 0, "text": title, "parent": None},
                {"key": 1, "text": "المفاهيم الأساسية", "parent": 0, "brush": "turquoise"},
                {"key": 2, "text": "التطبيقات", "parent": 0, "brush": "turquoise"},
                {"key": 3, "text": "التعريفات", "parent": 1},
                {"key": 4, "text": "أمثلة", "parent": 2},
            ],
        }, ensure_ascii=False)

    if kind == "summary":
        return (
            f"افتتاحية\n في هذا الدرس نتناول {title} خطوة بخطوة.\n"
            f"خلاصة\n تعرّفنا على المفاهيم الأساسية لـ {title} وتطبيقاتها.\n"
            f"خاتمة\n بهذا نكتمل درسنا حول {title}."
        )

    # mindmap planning pass (result is discarded by MindMapTemplate)
    return f"خطة بناء الخريطة الذهنية لـ {title}: مفاهيم، تطبيقات، أمثلة."


class FakeChatModel(BaseChatModel):
    """Deterministic offline stand-in for an OpenRouter chat model."""

    model_label: str = "fake"

    @property
    def _llm_type(self) -> str:
        return "fake-openrouter"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        prompt_text = "\n".join(str(m.content) for m in messages)
        kind = _detect_prompt_kind(prompt_text)
        CALL_LOG.append({"model": self.model_label, "stage": kind})
        return ChatResult(generations=[
            ChatGeneration(message=AIMessage(content=_craft_response(kind, prompt_text)))
        ])


def _fake_create_chat_model(model_name=None, temperature=None, api_key=None) -> FakeChatModel:
    return FakeChatModel(model_label=model_name or Settings.NON_MATH_MODEL)


def install_fake_models():
    """Route every chat-model creation in the pipeline to the fake models."""
    import clients.llm_client as llm_client
    import generators.template_generator as template_generator_module
    import processors.content_processor as content_processor_module
    import template.base_template as base_template_module

    for module in (llm_client, template_generator_module,
                   content_processor_module, base_template_module):
        module.create_chat_model = _fake_create_chat_model


# --------------------------------------------------------------------------
# Full AI Cycle demo
# --------------------------------------------------------------------------
def select_demo_lessons(bundles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Pick one math lesson and one non-math lesson to show model routing."""
    math_lesson = next((b for b in bundles if "رياضيات" in (b.get("subject_title") or "")), None)
    other_lesson = next((b for b in bundles if b is not math_lesson
                         and "رياضيات" not in (b.get("subject_title") or "")), None)
    return [b for b in (math_lesson, other_lesson) if b]


def print_model_of(result: Dict[str, Any]):
    selected = (result or {}).get("_metadata", {}).get("selected_model", "?")
    print(f"   🤖 OpenRouter model: {selected}")


def run_cycle(generator: TemplateGenerator, document: Dict[str, Any]):
    """Run the Full AI Cycle on one lesson (questions-as-content)."""
    content = document["content"]

    print("\n" + "=" * 70)
    print(f"📗 LESSON: {document['filename']}  ({document['uuid']})")
    print("=" * 70)
    print("── STAGE 0: content = lesson questions (from MongoDB tahdiri) ──")
    print(f"   {len(content)} chars of questions-as-content")
    print(content[:PREVIEW_CHARS])
    print("   ...")

    print("\n── STAGE 1: content analysis + model routing ──")
    analysis = generator.get_content_analysis(content)
    print(f"   subject_area: {analysis['subject_area']}, "
          f"is_mathematical: {analysis['is_mathematical']}, "
          f"language: {analysis['language']}")
    print(f"   ➜ routed to: {generator._select_model_name(analysis)}")

    print("\n── STAGE 2: summary ──")
    summary = generator.generate_summary(content)
    print(f"   opening: {summary.get('opening', '')[:80]}...")
    print_model_of(summary)

    print("\n── STAGE 3: learning goals ──")
    goals = generator.content_processor.generate_learning_goals(content, count=5)
    for i, goal in enumerate(goals, 1):
        print(f"   {i}. {goal}")

    print("\n── STAGE 4: worksheet ──")
    worksheet = generator.generate_worksheet(content, goals)
    structured = worksheet.get("structured_goals") or []
    if structured:
        goals = [g.get("text") for g in structured if g.get("text")] or goals
        print(f"   goals refined from worksheet: {len(goals)}")
    print(f"   applications: {len(worksheet.get('applications', []))}, "
          f"vocabulary: {len(worksheet.get('vocabulary', []))}, "
          f"teacher_guidelines: {len(worksheet.get('teacher_guidelines', []))}")
    print_model_of(worksheet)

    print("\n── STAGE 5: goal-based questions ──")
    questions = generator.generate_goal_based_questions(
        content=content,
        goals=goals,
        question_counts=DEMO_QUESTION_COUNTS,
        difficulty_levels=[1, 2],
    )
    goal_meta = questions.get("_goal_based_metadata", {})
    print(f"   scenario: {goal_meta.get('scenario', '?')}, "
          f"goals: {goal_meta.get('total_goals', 0)}, "
          f"questions: {goal_meta.get('total_questions', 0)}")
    sample = (questions.get("multiple_choice") or [{}])[0]
    print(f"   sample MCQ: {sample.get('question', '')[:80]}")
    print_model_of(questions)

    print("\n── STAGE 6: mind map ──")
    mindmap = generator.generate_mindmap(content)
    nodes = (mindmap or {}).get("nodeDataArray", [])
    root = next((n for n in nodes if n.get("parent") is None), {})
    print(f"   nodes: {len(nodes)}, root: {root.get('text', '?')}")
    print_model_of(mindmap)


def print_call_log():
    if not CALL_LOG:
        return
    print("\n" + "=" * 70)
    print("📊 OFFLINE MODEL CALL LOG (fake OpenRouter models)")
    print("=" * 70)
    totals: Dict[tuple, int] = {}
    for call in CALL_LOG:
        key = (call["model"], call["stage"])
        totals[key] = totals.get(key, 0) + 1
    for (model, stage), count in sorted(totals.items()):
        print(f"   {model:22s} stage={stage:16s} calls={count}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Full AI Cycle workflow demo (questions as content)")
    parser.add_argument("--live", action="store_true",
                        help="Use real OpenRouter models (requires OPENROUTER_API_KEY)")
    parser.add_argument("--lesson-source-id", type=int, nargs="*", default=None,
                        help="Specific lesson source id(s) to demo (default: one math + one non-math)")
    parser.add_argument("--min-questions", type=int, default=1,
                        help="Skip lessons with fewer questions than this")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.live:
        if Settings.OPENROUTER_API_KEY == "offline-demo-key":
            print("❌ --live requires OPENROUTER_API_KEY in the environment or .env")
            return 1
    else:
        print("🧪 Offline mode: deterministic fake models "
              "(use --live for real OpenRouter calls)")
        install_fake_models()

    tahdiri = TahdiriQuestionsClient()
    if not tahdiri.connect():
        return 1
    try:
        bundles = tahdiri.get_lesson_bundles(
            lesson_source_ids=args.lesson_source_id or None,
            min_questions=args.min_questions,
        )
        if not bundles:
            print("❌ No lessons with questions found")
            return 1

        if args.lesson_source_id:
            chosen = bundles
        else:
            chosen = select_demo_lessons(bundles)
            if not chosen:
                chosen = bundles[:2]

        generator = TemplateGenerator()
        for bundle in chosen:
            questions = tahdiri.get_questions_by_lesson(bundle["lesson_source_id"])
            document = {
                "uuid": f"tahdiri-{bundle['lesson_source_id']}",
                "filename": bundle["title"],
                "content": build_lesson_content(bundle, questions),
            }
            run_cycle(generator, document)
    finally:
        tahdiri.disconnect()

    print_call_log()
    print("\n✅ Workflow demo finished: questions (MongoDB) -> content -> "
          "summary -> goals -> worksheet -> goal-based questions -> mind map")
    return 0


if __name__ == "__main__":
    sys.exit(main())
