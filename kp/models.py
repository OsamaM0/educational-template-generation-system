"""Structured outputs for legacy archetype replay.

New open-format production schemas live in production_models.py.
All properties are required; archetype-specific fields are nullable.
"""
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

Archetype = Literal["cipher", "case_file", "blueprint"]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------- step A: topics
class Topic(_M):
    goal_id: str = Field(description="معرّف الهدف كما ورد تمامًا")
    archetype: Archetype
    title: str = Field(description="اسم قصير جذاب للموضوع الجديد، دون صف أو مدرسة")
    subtitle: str = Field(description="على نمط: من … إلى …")
    kind_line: str = Field(description="مثل: إنتاج معرفي تطبيقي في الأمن السيبراني")
    stage_label: str = Field(description="اسم المرحلة المفرد في القصة: البطاقة / الدليل / المحطة …")
    premise: str = Field(description="فكرة المنتج في ٢–٣ جمل")
    concept_transfer: str = Field(description="كيف تنتقل مفاهيم الهدف إلى الغاية الجديدة، وكيف تنتج الإجابات الناتج")
    concepts: List[str] = Field(description="المفاهيم التي ينقلها الموضوع")
    question_refs: List[str] = Field(description="معرّفات أسئلة البنك المختارة لهذا الموضوع")


class Topics(_M):
    topics: List[Topic]


# -------------------------------------------------------------- step B: project
class Intro(_M):
    story: List[str] = Field(description="فقرتان أو ثلاث تفتتح القصة")
    objective: str
    rules_title: str
    rules: List[str]


class Payoff(_M):
    title: str
    instruction: str
    solution: Optional[str] = Field(description="cipher فقط: كلمة واحدة بلا تشكيل؛ وإلا null")
    meaning: Optional[str] = Field(description="cipher فقط: معنى الكلمة؛ وإلا null")
    columns: Optional[List[str]] = Field(description="case_file فقط: أعمدة سجل الأدلة؛ وإلا null")
    verdict: Optional[str] = Field(description="case_file فقط: الحكم النهائي؛ وإلا null")
    layers: Optional[List[str]] = Field(description="blueprint فقط: عناوين الطبقات؛ وإلا null")


class Deliverable(_M):
    title: str
    columns: List[str]
    rows: List[str] = Field(description="قيمة العمود الأول لكل صف، أو نص فارغ لصف يكتبه المتعلم")
    model: List[List[str]] = Field(description="الصفوف مكتملة كنموذج إجابة، بعرض الأعمدة نفسه")


class Criterion(_M):
    criterion: str
    descriptor: str


class FinalTask(_M):
    title: str
    prompt: str
    deliverable: Deliverable
    rubric: List[Criterion]


class Titled(_M):
    title: str
    items: List[str]


class Reveal(_M):
    title: str
    story: str
    reference: Titled
    plan: Titled


class Project(_M):
    intro: Intro
    payoff: Payoff
    final_task: FinalTask
    reveal: Reveal


# ----------------------------------------------------------------- step C: link
class StageLink(_M):
    question_ref: str = Field(description="معرّف سؤال من القائمة، كما هو")
    question_text: str = Field(description="نص السؤال بلغة المنتج: ترجمة أمينة عند اختلاف اللغة (نفس المعنى ونفس ترتيب الخيارات)، وإلا النص كما هو")
    choices: Optional[List[str]] = Field(description="خيارات multiple_choice بنفس الترتيب بلغة المنتج؛ ولغيره null")
    answer_text: Optional[str] = Field(description="الإجابة بلغة المنتج للإكمال والإجابة القصيرة؛ وللصحيح/الخطأ والاختيار من متعدد null")
    title: str
    scene: str = Field(description="جملة أو جملتان تقودان إلى السؤال دون ذكر الإجابة")
    explanation: str = Field(description="جملة تفسر الإجابة الصحيحة")
    word_bank: Optional[List[str]] = Field(description="لأسئلة الإكمال: كلمتان خاطئتان معقولتان؛ وإلا null")
    finding: Optional[str] = Field(description="case_file: العلامة التي يدوّنها المتعلم؛ وإلا null")
    component: Optional[str] = Field(description="blueprint: القطعة المكتسبة؛ وإلا null")
    layer: Optional[str] = Field(description="blueprint: عنوان الطبقة حرفيًا؛ وإلا null")


class FinalQuestionLink(_M):
    question_ref: str = Field(description="معرّف سؤال المهمة النهائية كما ورد تمامًا")
    question_text: str = Field(description="نص السؤال بلغة المنتج")
    choices: Optional[List[str]] = Field(description="خيارات multiple_choice بنفس الترتيب بلغة المنتج؛ ولغيره null")
    answer_text: str = Field(description="الإجابة النموذجية بلغة المنتج")


class Link(_M):
    stages: List[StageLink]
    final_questions: List[FinalQuestionLink] = Field(
        description="كل سؤال مختار لم يُستخدم في المراحل، مترجمًا إلى لغة المنتج"
    )
