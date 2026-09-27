"""
MongoDB client for the 'tahdiri' question bank.

The content of a lesson for the Full AI Cycle is built from that lesson's
questions in `tahdiri.questions` (grouped by `lessonSourceId` and joined to
`tahdiri.lessons`) instead of the raw lesson text served by the document
(PostgreSQL-backed) API.
"""
from typing import Any, Dict, List, Optional

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

from clients.mongo_client import DEFAULT_MONGODB_URI

# Human-readable (Arabic) labels for the question types stored in `tahdiri`.
QUESTION_TYPE_LABELS = {
    "multiple_choice": "اختيار من متعدد",
    "true_false": "صح / خطأ",
    "fillinblank": "أكمل الفراغ",
    "essay": "سؤال مقالي",
    "matching": "صل بين العمودين",
    "ordering": "رتب العناصر",
    "wordblank": "أكمل الكلمة",
}

_CHOICE_LABELS = ["أ", "ب", "ج", "د", "هـ", "و", "ز"]
_TRUE_FALSE_LABELS = ["صح", "خطأ"]


def _format_answer(question: Dict[str, Any]) -> str:
    """Render the answer/model answer of a question as a single line."""
    q_type = question.get("type", "essay")
    answer = question.get("answer")

    if q_type == "multiple_choice" and isinstance(answer, int) and question.get("choices"):
        # Stored answers are 1-based indexes into `choices`
        position = answer - 1 if answer > 0 else 0
        choices = question["choices"]
        if 0 <= position < len(choices):
            return f"{answer}) {choices[position]}"
        return str(answer)

    if q_type == "true_false":
        if isinstance(answer, bool):
            return _TRUE_FALSE_LABELS[0] if answer else _TRUE_FALSE_LABELS[1]
        return str(answer)

    if q_type == "matching" and question.get("modelAnswer"):
        return str(question["modelAnswer"])

    return str(answer) if answer is not None else ""


def format_question(index: int, question: Dict[str, Any]) -> str:
    """Render one `tahdiri` question as readable lesson content lines."""
    q_type = question.get("type", "essay")
    label = QUESTION_TYPE_LABELS.get(q_type, q_type)
    lines = [f"{index}) [{label}] {str(question.get('question', '')).strip()}"]

    choices = question.get("choices") or []
    if choices:
        rendered = [
            f"   {_CHOICE_LABELS[i] if i < len(_CHOICE_LABELS) else i + 1}) {choice}"
            for i, choice in enumerate(choices)
        ]
        lines.extend(rendered)

    column_a = question.get("columnA") or []
    column_b = question.get("columnB") or []
    for i, item in enumerate(column_a):
        lines.append(f"   (أ{i + 1}) {item}")
    for i, item in enumerate(column_b):
        lines.append(f"   (ب{i + 1}) {item}")

    answer_line = _format_answer(question)
    if answer_line:
        lines.append(f"   الإجابة: {answer_line}")
    return "\n".join(lines)


def build_lesson_content(lesson: Dict[str, Any], questions: List[Dict[str, Any]]) -> str:
    """Build the lesson *content* (used by the Full AI Cycle) from its questions."""
    header_parts = filter(
        None,
        [lesson.get("subject_title"), lesson.get("unit_title"), lesson.get("grade_title")],
    )
    lines = [f"عنوان الدرس: {lesson.get('title', '')}"]
    hierarchy = " | ".join(header_parts)
    if hierarchy:
        lines.append(f"المنهج: {hierarchy}")
    lines.append("")
    lines.append(f"أسئلة الدرس ({len(questions)} سؤال):")
    lines.append("")

    for i, question in enumerate(questions, 1):
        lines.append(format_question(i, question))
        lines.append("")

    return "\n".join(lines).strip()


class TahdiriQuestionsClient:
    """Client for reading lesson questions from the `tahdiri` database."""

    def __init__(self, connection_string: str = DEFAULT_MONGODB_URI):
        self.connection_string = connection_string
        self.client: Optional[MongoClient] = None
        self.db = None

    def connect(self) -> bool:
        """Establish connection to the `tahdiri` database."""
        try:
            self.client = MongoClient(self.connection_string)
            self.client.admin.command("ping")
            self.db = self.client["tahdiri"]
            print("✅ Tahdiri MongoDB connection established")
            return True
        except ConnectionFailure as e:
            print(f"❌ Tahdiri MongoDB connection failed: {str(e)}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error connecting to Tahdiri MongoDB: {str(e)}")
            return False

    def disconnect(self):
        """Close the MongoDB connection."""
        if self.client:
            self.client.close()
            print("🔒 Tahdiri MongoDB connection closed")

    def get_lesson_bundles(
        self,
        lesson_source_ids: Optional[List[int]] = None,
        limit: Optional[int] = None,
        min_questions: int = 1,
    ) -> List[Dict[str, Any]]:
        """Return lessons (with curriculum hierarchy) and their question counts.

        Args:
            lesson_source_ids: Restrict to these `lessons.sourceId` values
            limit: Maximum number of lessons to return
            min_questions: Skip lessons with fewer questions than this

        Returns:
            List of lesson bundles:
            {lesson_source_id, lesson_id, title, subject_title, unit_title,
             grade_title, question_count}
        """
        if self.db is None:
            print("❌ Tahdiri MongoDB not connected")
            return []

        match: Dict[str, Any] = {"active": {"$ne": False}, "lessonSourceId": {"$ne": None}}
        if lesson_source_ids:
            match["lessonSourceId"] = {"$in": lesson_source_ids}

        pipeline = [
            {"$match": match},
            {"$group": {"_id": "$lessonSourceId", "question_count": {"$sum": 1}}},
            {"$match": {"question_count": {"$gte": min_questions}}},
            {"$sort": {"_id": 1}},
        ]
        if limit:
            pipeline.append({"$limit": limit})

        counts = list(self.db["questions"].aggregate(pipeline))
        return self._hydrate_lessons(counts)

    def _hydrate_lessons(self, counts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Attach lesson titles and curriculum hierarchy to question counts."""
        source_ids = [row["_id"] for row in counts]
        lessons = {
            lesson["sourceId"]: lesson
            for lesson in self.db["lessons"].find({"sourceId": {"$in": source_ids}})
        }
        unit_ids = {l.get("unitSourceId") for l in lessons.values() if l.get("unitSourceId") is not None}
        units = {
            unit["sourceId"]: unit
            for unit in self.db["units"].find({"sourceId": {"$in": list(unit_ids)}})
        }
        subject_ids = {u.get("subjectSourceId") for u in units.values() if u.get("subjectSourceId") is not None}
        subjects = {
            s["sourceId"]: s
            for s in self.db["subjects"].find({"sourceId": {"$in": list(subject_ids)}})
        }
        term_ids = {s.get("termSourceId") for s in subjects.values() if s.get("termSourceId") is not None}
        terms = {
            t["sourceId"]: t
            for t in self.db["terms"].find({"sourceId": {"$in": list(term_ids)}})
        }
        grade_ids = {t.get("gradeSourceId") for t in terms.values() if t.get("gradeSourceId") is not None}
        grades = {
            g["sourceId"]: g
            for g in self.db["grades"].find({"sourceId": {"$in": list(grade_ids)}})
        }

        bundles = []
        for row in counts:
            source_id = row["_id"]
            lesson = lessons.get(source_id, {})
            unit = units.get(lesson.get("unitSourceId"), {})
            subject = subjects.get(unit.get("subjectSourceId"), {})
            term = terms.get(subject.get("termSourceId"), {})
            grade = grades.get(term.get("gradeSourceId"), {})
            bundles.append({
                "lesson_source_id": source_id,
                "lesson_id": str(lesson["_id"]) if lesson else None,
                "title": lesson.get("title") or f"Lesson {source_id}",
                "unit_title": unit.get("title"),
                "subject_title": subject.get("title"),
                "grade_title": grade.get("title"),
                "question_count": row["question_count"],
            })
        return bundles

    def get_questions_by_lesson(self, lesson_source_id: int) -> List[Dict[str, Any]]:
        """Fetch all active questions of one lesson, grouped by type order."""
        if self.db is None:
            print("❌ Tahdiri MongoDB not connected")
            return []
        cursor = self.db["questions"].find(
            {"lessonSourceId": lesson_source_id, "active": {"$ne": False}}
        ).sort("type", 1)
        return list(cursor)

    def get_source_ids_by_api_ids(self, api_lesson_ids: List[Any]) -> Dict[str, List[int]]:
        """Map ien-v2 lessonId -> tahdiri `lessons.sourceId` list.

        The join key between the two systems is `lessons.apiSourceId`
        (= ien-v2 `lessons.lessonId`); `questions.lessonSourceId` refers to
        tahdiri's own `lessons.sourceId`. One api id may map to several
        tahdiri lessons (split lessons).
        """
        mapping: Dict[str, List[int]] = {}
        if self.db is None or not api_lesson_ids:
            return mapping
        # match both int and str storage forms of the same id
        ids = []
        for value in api_lesson_ids:
            ids.append(value)
            ids.append(str(value))
            try:
                ids.append(int(value))
            except (TypeError, ValueError):
                pass
        for start in range(0, len(ids), 200):
            chunk = ids[start:start + 200]
            for lesson in self.db["lessons"].find(
                {"apiSourceId": {"$in": chunk}}, {"sourceId": 1, "apiSourceId": 1}
            ):
                api_id = lesson.get("apiSourceId")
                source_id = lesson.get("sourceId")
                if api_id is not None and source_id is not None:
                    mapping.setdefault(str(api_id), []).append(int(source_id))
        return mapping

    def get_questions_for_api_lesson(self, lesson_id: Any) -> List[Dict[str, Any]]:
        """Fetch questions of one ien-v2 lesson (joined via lessons.apiSourceId)."""
        source_ids = self.get_source_ids_by_api_ids([lesson_id]).get(str(lesson_id), [])
        questions: List[Dict[str, Any]] = []
        for source_id in source_ids:
            questions.extend(self.get_questions_by_lesson(source_id))
        return questions

    def get_questions_by_lessons(
        self, lesson_source_ids: List[int], chunk_size: int = 200
    ) -> Dict[int, List[Dict[str, Any]]]:
        """Bulk-fetch questions for many lessons, grouped by lessonSourceId.

        Chunked `$in` scans keep remote round-trips low (one per 200 lessons)
        and bound cursor memory.
        """
        grouped: Dict[int, List[Dict[str, Any]]] = {}
        if self.db is None or not lesson_source_ids:
            return grouped
        for start in range(0, len(lesson_source_ids), chunk_size):
            chunk = lesson_source_ids[start:start + chunk_size]
            cursor = self.db["questions"].find(
                {"lessonSourceId": {"$in": chunk}, "active": {"$ne": False}}
            ).sort("type", 1)
            for question in cursor:
                grouped.setdefault(question.get("lessonSourceId"), []).append(question)
        return grouped

    def get_lesson_documents(
        self,
        lesson_source_ids: Optional[List[int]] = None,
        limit: Optional[int] = None,
        min_questions: int = 1,
    ) -> List[Dict[str, Any]]:
        """Build document-shaped dicts (questions-as-content) for the AI cycle.

        The shape matches the document contract consumed by BatchProcessor:
        {uuid, idx, custom_id, collection_id, filename, content}.
        """
        documents = []
        for bundle in self.get_lesson_bundles(lesson_source_ids, limit, min_questions):
            questions = self.get_questions_by_lesson(bundle["lesson_source_id"])
            if not questions:
                continue
            documents.append({
                "uuid": f"tahdiri-{bundle['lesson_source_id']}",
                "idx": str(bundle["lesson_source_id"]),
                "custom_id": str(bundle["lesson_source_id"]),
                "collection_id": None,
                "filename": bundle["title"],
                "content": build_lesson_content(bundle, questions),
            })
        return documents
