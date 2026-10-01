"""Open product forms; bounded content primitives for safe portable rendering.

product_type describes the educational resource freely. Block kinds describe
presentation, not the allowed types of knowledge production.
"""
from typing import Literal
from .models import _M


class ProductionTopic(_M):
    goal_id: str
    product_type: str
    title: str
    subtitle: str
    purpose: str
    audience: str
    lesson_connection: str
    concepts: list[str]
    layout: Literal['document', 'cards', 'poster']
    question_refs: list[str]


class ProductionTopics(_M):
    topics: list[ProductionTopic]


class Row(_M):
    cells: list[str]


class ContentBlock(_M):
    kind: Literal['paragraph', 'callout', 'bullets', 'steps', 'table', 'cards', 'question', 'response_space']
    title: str | None
    text: str | None
    items: list[str] | None
    columns: list[str] | None
    rows: list[Row] | None
    question_ref: str | None
    teacher_only: bool


class ProductionSection(_M):
    id: str
    title: str
    role: str
    blocks: list[ContentBlock]


class ProductionProject(_M):
    sections: list[ProductionSection]


class QuestionDisplay(_M):
    question_ref: str
    question_text: str
    choices: list[str] | None
    answer_text: str
    explanation: str


class ProductionLinks(_M):
    questions: list[QuestionDisplay]
