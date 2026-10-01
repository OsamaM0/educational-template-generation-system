"""The question bank of one lesson, as the renderer will see it.

Worksheet goals are authoritative. ``ai.questions`` contributes cognitive
metadata and explicit ``goal_id`` / ``target_goal`` links when present. Untagged
questions are exposed as semantic-selection candidates, but a question tagged
for another goal is never offered.

Question ids MUST equal what server/pipeline/source.mjs derives, because a
stored product only references questions by id:
    stored id (id | question_id | questionId | qid) if present,
    else  prefix + "_" + (raw position in that kind's list + 1),
    repeats suffixed _2, _3 … across the whole lesson,
    kinds processed in the order mc, tf, cp, sa.
"""
import hashlib, json, re
from dataclasses import dataclass, field

KINDS = [("multiple_choice", "mc"), ("true_false", "tf"), ("complete", "cp"), ("short_answer", "sa")]
TF = ["صح", "خطأ"]


def _s(v):
    return v.strip() if isinstance(v, str) else ("" if v is None else str(v))


@dataclass
class Question:
    id: str
    kind: str
    text: str
    choices: list
    answer_key: object
    answer: str
    difficulty: int
    goal_id: str
    target_goal: str

    @property
    def answer_text(self):
        if self.kind == "multiple_choice":
            k = self.answer_key
            return self.choices[k] if isinstance(k, int) and 0 <= k < len(self.choices) else self.answer
        if self.kind == "true_false":
            return TF[1 if self.answer_key == 1 else 0]
        return self.answer

    @property
    def gradable(self):
        """Has exactly one checkable answer — usable in a cipher / as a stage."""
        if self.kind == "multiple_choice":
            return isinstance(self.answer_key, int) and 0 <= self.answer_key < len(self.choices) and len(self.choices) >= 2
        if self.kind == "true_false":
            return self.answer_key in (0, 1)
        if self.kind == "complete":
            blanks = len(re.findall(r"_{3,}", self.text))
            return blanks <= 1 and bool(self.answer) and not re.search(r"[,،]", self.answer) and len(self.answer) <= 30
        return False

    def for_prompt(self):
        d = {"id": self.id, "kind": self.kind, "text": self.text, "answer": self.answer_text}
        if self.kind == "multiple_choice":
            d["choices"] = self.choices
        return d


@dataclass
class Goal:
    id: str
    text: str
    cognitive_level: str
    questions: list = field(default_factory=list)

    @property
    def gradable(self):
        return [q for q in self.questions if q.gradable]

    @property
    def open(self):
        return [q for q in self.questions if not q.gradable]


@dataclass
class Bank:
    record: dict
    goals: list
    index: dict

    @property
    def fingerprint(self):
        blob = json.dumps(self.record.get("questions", {}), ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]

    @property
    def subject(self):
        meta = (self.record.get("questions", {}).get("_metadata") or {}).get("content_analysis") or {}
        return _s(meta.get("subject"))

    def candidates_for(self, goal):
        """Questions explicitly tied to this goal plus safe untagged questions.

        A question tagged for another goal is never offered to the model. Older
        banks without ``goal_id`` remain usable: ``target_goal`` is matched to
        worksheet goal text during normalization, and truly untagged questions
        may be selected semantically from their text.
        """
        exact = list(goal.questions)
        untagged = [q for q in self.index.values() if not q.goal_id]
        seen = {q.id for q in exact}
        return exact + [q for q in untagged if q.id not in seen]


def _norm_goal(text):
    return " ".join(_s(text).split()).rstrip(".؟")


def build_bank(record, goal_texts=None):
    q = record.get("questions") or {}
    index, seen = {}, set()
    for kind, prefix in KINDS:
        for i, raw in enumerate(q.get(kind) or []):
            if not isinstance(raw, dict):
                continue
            text = _s(raw.get("question") or raw.get("text") or raw.get("prompt"))
            if not text:
                continue                                    # skipped, but position still counts
            qid = _s(raw.get("id") or raw.get("question_id") or raw.get("questionId") or raw.get("qid")) or f"{prefix}_{i + 1}"
            if qid in seen:
                n = 2
                while f"{qid}_{n}" in seen:
                    n += 1
                qid = f"{qid}_{n}"
            seen.add(qid)
            ak = raw.get("answer_key", raw.get("answerKey"))
            try:
                ak = int(ak) if ak is not None else None
            except (TypeError, ValueError):
                ak = None
            index[qid] = Question(
                id=qid, kind=kind, text=text,
                choices=[_s(c) for c in (raw.get("choices") or raw.get("options") or []) if _s(c)],
                answer_key=ak, answer=_s(raw.get("answer") or raw.get("model_answer")),
                difficulty=int(raw.get("difficulty") or 1), goal_id=_s(raw.get("goal_id") or raw.get("goalId")),
                target_goal=_s(raw.get("target_goal") or raw.get("targetGoal")))

    raw_goals = q.get("learning_goals") or []
    question_goals = [Goal(id=_s(g.get("id")) or f"goal_{i + 1}", text=_s(g.get("text")),
                           cognitive_level=_s(g.get("cognitive_level")) or "understand")
                      for i, g in enumerate(raw_goals) if _s(g.get("text"))]

    if goal_texts:
        # worksheet.goals is authoritative. Preserve question-bank ids and
        # cognitive levels by exact text first, then by position.
        available = list(question_goals)
        goals = []
        for i, text in enumerate(goal_texts):
            text = _s(text)
            match = next((g for g in available if _norm_goal(g.text) == _norm_goal(text)), None)
            if match is None and i < len(question_goals) and question_goals[i] in available:
                match = question_goals[i]
            if match is not None:
                available.remove(match)
            goals.append(Goal(id=match.id if match else f"goal_{i + 1}", text=text,
                              cognitive_level=match.cognitive_level if match else "understand"))
    else:
        goals = question_goals

    if not goals:  # older records: flat goal strings, questions still tagged goal_N
        goals = [Goal(id=f"goal_{i + 1}", text=_s(t), cognitive_level="understand")
                 for i, t in enumerate(record.get("goals") or []) if _s(t)]
    by_id = {g.id: g for g in goals}
    by_text = {_norm_goal(g.text): g for g in goals}
    for qu in index.values():
        goal = by_id.get(qu.goal_id)
        if goal is None and qu.target_goal:
            goal = by_text.get(_norm_goal(qu.target_goal))
            if goal is not None:
                qu.goal_id = goal.id
        if goal is not None:
            goal.questions.append(qu)
    return Bank(record=record, goals=goals, index=index)
