"""MongoDB lesson source for knowledge-production generation.

The generator deliberately uses the same ``ai`` database as the worksheet
platform:

* ``summaries`` provides the grounded lesson text
  (``summary.opening``, ``summary.summary`` and ``summary.ending``).
* ``worksheets`` provides the authoritative list of goals
  (``worksheet.goals``).

Questions are loaded separately by :mod:`kp.store`, because they keep their
own fingerprint and validation rules. PostgreSQL and the Documents API are not
part of this pipeline.
"""
from dataclasses import dataclass, field
import hashlib
import json
import re

ID_TYPES = ("idx", "uuid", "custom_id")

_ARABIC_SCRIPT = re.compile(r"[\u0600-\u06FF]")
_LATIN_SCRIPT = re.compile(r"[A-Za-z]")


def detect_language(*texts):
    """The lesson's own language, decided by its goals and title.

    The summary is deliberately NOT part of the vote: it is routinely Arabic
    whatever the lesson teaches, and an English lesson must still produce an
    English product.
    """
    blob = " ".join(t for t in texts if t)
    return "en" if len(_LATIN_SCRIPT.findall(blob)) > len(_ARABIC_SCRIPT.findall(blob)) else "ar"


def _language_code(value):
    value = str(value or "").strip().lower()
    if value in {"en", "eng", "english", "الإنجليزية", "الانجليزية"}:
        return "en"
    if value in {"ar", "ara", "arabic", "العربية", "العربيه"}:
        return "ar"
    return ""


def _text(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(_text(v) for v in value if _text(v))
    return "" if value is None else str(value).strip()


def _strings(value):
    return [_text(v) for v in value] if isinstance(value, list) else []


def _identity_filter(lesson_id, id_type):
    if id_type not in ID_TYPES:
        raise ValueError(f"id_type must be one of {ID_TYPES}")
    field_name = {"idx": "document_idx", "uuid": "document_uuid", "custom_id": "custom_id"}[id_type]
    value = str(lesson_id).strip()
    values = [value]
    if id_type == "idx" and value.isdigit():
        values.append(int(value))
    return {field_name: {"$in": values}}


def _same_lesson_filter(doc):
    if doc.get("document_uuid"):
        return {"document_uuid": str(doc["document_uuid"])}
    if doc.get("document_idx") is not None:
        return _identity_filter(doc["document_idx"], "idx")
    if doc.get("custom_id"):
        return {"custom_id": str(doc["custom_id"])}
    return {"_id": doc.get("_id")}


@dataclass
class ContentDoc:
    uuid: str
    idx: str
    custom_id: str
    title: str
    content: str
    goals: list[str] = field(default_factory=list)
    language_hint: str = ""

    @property
    def language(self):
        return _language_code(self.language_hint) or detect_language(self.title, *self.goals)

    @property
    def fingerprint(self):
        # A worksheet-goal change must invalidate an otherwise unchanged
        # summary, because the product unit is one booklet per goal.
        blob = json.dumps({"title": self.title, "content": self.content, "goals": self.goals,
                           "language": self.language}, ensure_ascii=False, sort_keys=True)
        return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


class ContentNotFound(LookupError):
    pass


class MongoSummaryContent:
    """Read summary content and worksheet goals from the configured ``ai`` DB."""

    def __init__(self, settings, db):
        self.s, self.db = settings, db

    def get(self, lesson_id, id_type="idx"):
        lookup = _identity_filter(lesson_id, id_type)
        summary_doc = self.db[self.s.col_summaries].find_one(lookup)
        if not summary_doc:
            raise ContentNotFound(
                f"no ai.{self.s.col_summaries} record for {id_type}={lesson_id}"
            )

        summary = summary_doc.get("summary") or {}
        if isinstance(summary, str):
            body = summary.strip()
        else:
            parts = [
                ("التمهيد", _text(summary.get("opening"))),
                ("ملخص الدرس", _text(summary.get("summary") or summary.get("body"))),
                ("الخلاصة", _text(summary.get("ending"))),
            ]
            body = "\n\n".join(f"{label}:\n{text}" for label, text in parts if text)
        if len(body) < 20:
            raise ContentNotFound(
                f"summary content for {id_type}={lesson_id} is empty"
            )

        worksheet_doc = self.db[self.s.col_worksheets].find_one(_same_lesson_filter(summary_doc))
        worksheet = (worksheet_doc or {}).get("worksheet") or {}
        # Worksheet goals are authoritative. A root-level worksheet goals array
        # is accepted for older worksheet records; summary/question goals are
        # intentionally not substitutes.
        goals = [g for g in _strings(worksheet.get("goals")) if g]
        if not goals:
            goals = [g for g in _strings((worksheet_doc or {}).get("goals")) if g]

        identity = worksheet_doc or summary_doc
        worksheet_meta = worksheet.get("_metadata") if isinstance(worksheet.get("_metadata"), dict) else {}
        content_analysis = worksheet_meta.get("content_analysis") if isinstance(worksheet_meta.get("content_analysis"), dict) else {}
        language_hint = worksheet_meta.get("language") or content_analysis.get("language") or ""
        return ContentDoc(
            uuid=str(summary_doc.get("document_uuid") or identity.get("document_uuid") or ""),
            idx=str(summary_doc.get("document_idx") or identity.get("document_idx") or ""),
            custom_id=str(summary_doc.get("custom_id") or identity.get("custom_id") or ""),
            title=_text((worksheet_doc or {}).get("filename") or summary_doc.get("filename") or identity.get("filename")) or f"درس {lesson_id}",
            content=body,
            goals=goals,
            language_hint=_text(language_hint),
        )

    def close(self):
        # The CLI owns the shared MongoClient; this source owns no connection.
        pass


def open_content(settings, db):
    return MongoSummaryContent(settings, db)
