"""
Repair tool for the "labels-only wrong" bucket found during the goals-source
audit (see get_goals_by_custom_id fix in clients/mongo_client.py).

Background:
  Some worksheets/questions were generated using goals fetched from the
  legacy `ien.lessonplangoals` collection, which turned out to associate the
  wrong lesson's goals with a document's custom_id. For most affected
  documents the wrong goals also dragged the generated question/worksheet
  content off-topic (those need full regeneration -- see both_wrong_uuids.json
  and bulk_generator.py --uuid-file). But for a subset, the actual generated
  question/worksheet content stayed correctly on-topic (the model favored the
  real `content` over the wrong `goals` when writing the questions) -- only
  the `goals` field and each question's target_goal/goal_id labels are wrong.

This script fixes that second bucket cheaply: for each affected document, it
fetches the CORRECT goals (via the now-fixed get_goals_by_custom_id), then
asks the model to re-sort the EXISTING questions against the correct goal
list (one lightweight call, no new questions written), and rewrites the
goals/label fields in place.

Usage:
    python repair_goal_labels.py --uuid-file labels_only_uuids.json --dry-run
    python repair_goal_labels.py --uuid-file labels_only_uuids.json --commit
"""
import argparse
import json
import sys
from typing import Any, Dict, List

from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI
from clients.llm_client import create_chat_model

from clients.mongo_client import MongoDBClient
from config.settings import Settings


RELABEL_PROMPT_AR = """أنت خبير مناهج تعليمية. لديك قائمة أسئلة موجودة بالفعل لدرس معيّن، وقائمة "الأهداف التعليمية الصحيحة" لهذا الدرس (وهي مختلفة عن الأهداف التي كانت مستخدمة سابقًا وأدت إلى تصنيف خاطئ).

مهمتك: لكل سؤال، حدد أي هدف من "الأهداف الصحيحة" يخدمه هذا السؤال بشكل أفضل (استنادًا إلى نص السؤال نفسه، وليس إلى الهدف الخاطئ المرفق به سابقًا). لا تُعدّل نص الأسئلة إطلاقًا.

الأهداف الصحيحة:
{goals}

الأسئلة (كل سؤال له index رقمي):
{questions}

أعد إجابة بصيغة JSON فقط بهذا الشكل بالضبط:
{{"assignments": [{{"index": 0, "goal_index": 1}}, ...]}}
حيث goal_index هو رقم الهدف في قائمة "الأهداف الصحيحة" أعلاه (يبدأ من 0). لا تُضِف أي نص آخر خارج الـ JSON."""

RELABEL_PROMPT_EN = """You are an expert curriculum designer. You have an existing list of questions for a lesson, and a list of the CORRECT learning goals for that lesson (different from the goals previously used, which caused mislabeling).

Task: for each question, decide which of the correct goals it best serves (based on the question text itself, not the wrong goal it was previously tagged with). Do NOT modify the question text.

Correct goals:
{goals}

Questions (each has a numeric index):
{questions}

Respond ONLY as strict JSON in exactly this shape:
{{"assignments": [{{"index": 0, "goal_index": 1}}, ...]}}
where goal_index is the position (0-based) in the "Correct goals" list above. No extra text."""


def flatten_questions(questions_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten the 4 question-type arrays into one list, remembering (type, position)."""
    flat = []
    for qtype in ["multiple_choice", "short_answer", "complete", "true_false"]:
        for pos, q in enumerate(questions_doc.get(qtype, []) or []):
            flat.append({"type": qtype, "pos": pos, "question": q.get("question", "")})
    return flat


def is_arabic(text: str) -> bool:
    return any('؀' <= ch <= 'ۿ' for ch in text)


def get_goal_assignments(model: ChatOpenAI, goals: List[str], flat_questions: List[Dict[str, Any]]) -> Dict[int, int]:
    lang_ar = is_arabic(" ".join(goals) or (flat_questions[0]["question"] if flat_questions else ""))
    template = RELABEL_PROMPT_AR if lang_ar else RELABEL_PROMPT_EN

    goals_block = "\n".join(f"{i}. {g}" for i, g in enumerate(goals))
    questions_block = "\n".join(f"{i}. {q['question']}" for i, q in enumerate(flat_questions))

    prompt = template.format(goals=goals_block, questions=questions_block)
    response = model.invoke(prompt)
    raw = getattr(response, "content", str(response))

    parser = JsonOutputParser()
    try:
        data = parser.parse(raw)
    except Exception:
        start, end = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[start:end + 1])

    assignments = {}
    for item in data.get("assignments", []):
        idx = item.get("index")
        gidx = item.get("goal_index")
        if isinstance(idx, int) and isinstance(gidx, int) and 0 <= gidx < len(goals):
            assignments[idx] = gidx
    return assignments


def rebuild_questions_doc(questions_doc: Dict[str, Any], goals: List[str], assignments: Dict[int, int]) -> Dict[str, Any]:
    goal_ids = [f"goal_{i+1}" for i in range(len(goals))]
    flat = flatten_questions(questions_doc)

    per_goal_counts: Dict[str, Dict[str, int]] = {gid: {"multiple_choice": 0, "short_answer": 0, "complete": 0, "true_false": 0} for gid in goal_ids}
    by_goal: Dict[str, Dict[str, List[Dict[str, Any]]]] = {gid: {"multiple_choice": [], "short_answer": [], "complete": [], "true_false": []} for gid in goal_ids}

    for flat_idx, meta in enumerate(flat):
        gidx = assignments.get(flat_idx, 0)  # default to first goal if the model skipped one
        gid = goal_ids[gidx]
        q_ref = questions_doc[meta["type"]][meta["pos"]]
        q_ref["target_goal"] = goals[gidx]
        q_ref["goal_id"] = gid
        per_goal_counts[gid][meta["type"]] += 1
        by_goal[gid][meta["type"]].append(q_ref)

    questions_doc["learning_goals"] = [
        {"id": gid, "text": goals[i], "priority": 1, "cognitive_level": "understand"}
        for i, gid in enumerate(goal_ids)
    ]
    questions_doc["goal_question_mapping"] = [
        {
            "goal_id": gid,
            "goal_text": goals[i],
            "question_count": sum(per_goal_counts[gid].values()),
            "question_types": per_goal_counts[gid],
        }
        for i, gid in enumerate(goal_ids)
    ]
    questions_doc["questions_by_goal"] = by_goal
    if "_goal_based_metadata" in questions_doc:
        questions_doc["_goal_based_metadata"]["total_goals"] = len(goals)
    return questions_doc


def rebuild_worksheet_doc(worksheet_doc: Dict[str, Any], goals: List[str]) -> Dict[str, Any]:
    """Worksheet goals are simpler (no per-question labels) -- just replace the
    top-level goals list. structured_goals/goal_based_activities are dropped
    rather than guessed, since their activities/assessment text was written
    for the wrong goals and can't be safely relabeled without regenerating them."""
    worksheet_doc["goals"] = goals
    worksheet_doc.pop("structured_goals", None)
    worksheet_doc.pop("goal_based_activities", None)
    return worksheet_doc


def main():
    parser = argparse.ArgumentParser(description="Relabel goals for documents whose content is correct but goals/labels are wrong")
    parser.add_argument("--uuid-file", required=True, help="JSON file with a list of document_uuid strings")
    parser.add_argument("--commit", action="store_true", help="Actually write changes (default is dry-run)")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N uuids (for testing)")
    args = parser.parse_args()

    with open(args.uuid_file, encoding="utf-8") as f:
        uuids = json.load(f)
    if args.limit:
        uuids = uuids[: args.limit]

    Settings.validate_config()
    model = create_chat_model(temperature=0)

    mongo = MongoDBClient()
    if not mongo.connect():
        sys.exit(1)

    n_ok, n_skipped, n_err = 0, 0, 0
    for uuid in uuids:
        w_doc = mongo.storage_db["worksheets"].find_one({"document_uuid": uuid})
        q_doc = mongo.storage_db["questions"].find_one({"document_uuid": uuid})
        if not w_doc and not q_doc:
            print(f"⚠️ {uuid}: no worksheet/questions found, skipping")
            n_skipped += 1
            continue

        custom_id = (w_doc or q_doc).get("custom_id")
        filename = (w_doc or q_doc).get("filename")
        correct_goals = mongo.get_goals_by_custom_id(custom_id) if custom_id else []
        if not correct_goals:
            print(f"⚠️ {uuid} ({filename}): no correct goals resolvable, skipping")
            n_skipped += 1
            continue

        try:
            if q_doc and q_doc.get("questions"):
                flat = flatten_questions(q_doc["questions"])
                assignments = get_goal_assignments(model, correct_goals, flat) if flat else {}
                new_questions = rebuild_questions_doc(q_doc["questions"], correct_goals, assignments)
                if args.commit:
                    mongo.storage_db["questions"].update_one(
                        {"_id": q_doc["_id"]},
                        {"$set": {"goals": correct_goals, "questions": new_questions}},
                    )
                print(f"✅ {uuid} ({filename}): questions relabeled ({len(flat)} questions)")

            if w_doc and w_doc.get("worksheet"):
                new_worksheet = rebuild_worksheet_doc(w_doc["worksheet"], correct_goals)
                if args.commit:
                    mongo.storage_db["worksheets"].update_one(
                        {"_id": w_doc["_id"]},
                        {"$set": {"goals": correct_goals, "worksheet": new_worksheet}},
                    )
                print(f"✅ {uuid} ({filename}): worksheet goals replaced")

            n_ok += 1
        except Exception as e:
            print(f"❌ {uuid} ({filename}): {e}")
            n_err += 1

    mode = "COMMITTED" if args.commit else "DRY RUN (no changes written -- pass --commit to apply)"
    print(f"\n{mode}: ok={n_ok} skipped={n_skipped} errors={n_err} / {len(uuids)} total")


if __name__ == "__main__":
    main()
