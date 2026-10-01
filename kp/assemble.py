"""Model outputs → the stored product (the shape build/knowledge-production.mjs reads).

Everything that can be computed is computed here rather than asked of the model:
  - cipher tokens: the correct choice of stage i carries letter i of the
    solution; decoys are drawn from the rest of the alphabet with a seeded RNG.
    A model asked to keep six letters consistent across six stages gets it
    wrong often; code never does.
  - word banks: the answer is always added by code, then shuffled with a seed,
    so the answer cannot be missing and the position is stable across runs.
  - final-task questions: every bank question of the goal not used as a stage.
"""
import hashlib, random
from .validate import cipher_letters

ALPHABETS = {"ar": list("ابتثجحخدذرزسشصضطظعغفقكلمنهوي"),
             "en": list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")}
TF_DISPLAY = {"ar": ["ص", "خ"], "en": ["T", "F"]}
REGISTRATION = {"ar": {"type": "كتاب إلكتروني", "language": "العربية", "origin": "داخلي"},
                "en": {"type": "E-book", "language": "English", "origin": "Internal"}}


def _rng(*parts):
    return random.Random(int(hashlib.sha1(":".join(map(str, parts)).encode()).hexdigest()[:12], 16))


def _word_bank(answer, distractors, rng):
    options = [answer] + [d.strip() for d in (distractors or []) if d and d.strip() and d.strip() != answer]
    options = list(dict.fromkeys(options))[:3]
    rng.shuffle(options)
    return options


def _right_index(q, seq, answer):
    """Which displayed option is correct — by key when the bank has one."""
    if q.kind == "true_false":
        return 1 if q.answer_key == 1 else 0
    if q.kind == "multiple_choice" and isinstance(q.answer_key, int):
        return q.answer_key if 0 <= q.answer_key < len(seq) else -1
    try:
        return list(seq).index(answer)
    except ValueError:
        return -1


def assemble(doc, goal, topic, project, link, bank, selected_questions, year):
    arch, payoff_in = topic["archetype"], project["payoff"]
    lang = doc.language or "ar"
    letters = cipher_letters(payoff_in.get("solution")) if arch == "cipher" else []
    stages = []
    for i, s in enumerate(link["stages"]):
        q = bank.index.get(s["question_ref"])
        y = {}
        rng = _rng(doc.uuid, goal.id, i)
        # What the product PRINTS: the bank question in the lesson's language
        # (prompts.link translates; derive what is derivable, ask for the rest).
        if q is not None and q.kind == "true_false":
            disp_choices = TF_DISPLAY[lang]
            disp_answer = TF_DISPLAY[lang][1 if q.answer_key == 1 else 0]
        elif q is not None and q.kind == "multiple_choice":
            given = [c.strip() for c in (s.get("choices") or []) if isinstance(c, str) and c.strip()]
            disp_choices = given if q.choices and len(given) == len(q.choices) else q.choices
            key = q.answer_key if isinstance(q.answer_key, int) and 0 <= q.answer_key < len(disp_choices) else None
            disp_answer = (s.get("answer_text") or "").strip() or (disp_choices[key] if key is not None else q.answer_text)
        else:
            disp_choices = None
            disp_answer = (s.get("answer_text") or "").strip() or (q.answer_text if q is not None else "")
        if q is not None and q.kind == "complete" and (s.get("word_bank") or arch == "cipher"):
            y["bank"] = _word_bank(disp_answer, s.get("word_bank"), rng)
        if arch == "cipher" and q is not None and q.gradable and i < len(letters):
            seq = disp_choices if disp_choices is not None else y.get("bank", [])
            right, pos = letters[i], _right_index(q, seq, disp_answer)
            decoys = rng.sample([a for a in ALPHABETS[lang] if a != right], max(0, len(seq) - 1))
            tokens, it = [], iter(decoys)
            for j in range(len(seq)):
                tokens.append(right if j == pos else next(it))
            y["tokens"] = tokens
        if arch == "case_file":
            y["finding"] = s.get("finding")
        if arch == "blueprint":
            y["component"], y["layer"] = s.get("component"), s.get("layer")
        stage = {"n": i + 1, "title": s["title"], "scene": s["scene"], "question_ref": s["question_ref"],
                 "mode": "reused", "question_text": (s.get("question_text") or "").strip() or (q.text if q is not None else ""),
                 "answer_text": disp_answer, "yields": y, "explanation": s["explanation"]}
        if disp_choices:
            stage["choices"] = list(disp_choices)
        stages.append(stage)

    used = {s["question_ref"] for s in stages}
    final_display = {d.get("question_ref"): d for d in (link.get("final_questions") or [])}
    open_questions = [q for q in selected_questions if q.id not in used]
    final_questions = []
    for q in open_questions[:3]:
        display = final_display.get(q.id) or {}
        choices = [c.strip() for c in (display.get("choices") or []) if isinstance(c, str) and c.strip()]
        if q.kind == "true_false":
            answer = TF_DISPLAY[lang][1 if q.answer_key == 1 else 0]
        elif q.kind == "multiple_choice" and len(choices) == len(q.choices):
            answer = choices[q.answer_key] if isinstance(q.answer_key, int) and 0 <= q.answer_key < len(choices) else ""
        else:
            answer = (display.get("answer_text") or "").strip() or q.answer_text
        item = {"question_ref": q.id,
                "question_text": (display.get("question_text") or "").strip() or q.text,
                "answer_text": answer}
        if q.kind == "multiple_choice":
            item["choices"] = choices if len(choices) == len(q.choices) else list(q.choices)
        final_questions.append(item)
    open_refs = [q["question_ref"] for q in final_questions]

    payoff = {"type": arch, "title": payoff_in["title"], "instruction": payoff_in["instruction"]}
    if arch == "cipher":
        payoff.update(solution="".join(letters), meaning=payoff_in.get("meaning"))
    elif arch == "case_file":
        payoff.update(columns=payoff_in.get("columns"), verdict=payoff_in.get("verdict"))
    else:
        payoff.update(layers=payoff_in.get("layers"))

    ft, d = project["final_task"], project["final_task"]["deliverable"]
    idea = {k: topic[k] for k in ("archetype", "title", "subtitle", "kind_line", "stage_label", "premise", "concept_transfer")}
    return {
        "id": f"kp_{goal.id}", "goal_id": goal.id, "goal_text": goal.text, "concepts": topic.get("concepts", []),
        "idea": idea,
        "intro": project["intro"],
        "stages": stages,
        "payoff": payoff,
        "final_task": {"title": ft["title"], "prompt": ft["prompt"], "question_refs": open_refs[:3],
                       "questions": final_questions,
                       "deliverable": {"title": d["title"], "columns": d["columns"],
                                       "rows": [r if isinstance(r, str) else "" for r in d["rows"]],
                                       # rows as {cells}: nested arrays are not portable
                                       # across Mongo-compatible servers (FerretDB v1 rejects them)
                                       "model": [{"cells": list(r)} for r in d["model"]]},
                       "rubric": ft["rubric"]},
        "reveal": project["reveal"],
        "registration": {"title": f"{topic['title']}: {topic['subtitle']}", "type": REGISTRATION[lang]["type"],
                         "main_class": None, "sub_class": None, "language": REGISTRATION[lang]["language"], "edition": 1,
                         "year": year, "parts": 1, "origin": REGISTRATION[lang]["origin"], "page_count": None,
                         "sensitive_topics": "none"},
    }
