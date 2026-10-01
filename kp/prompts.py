"""Legacy archetype prompts for replaying older records only.

New lesson generation uses production_prompts.py and open product types.
"""
import json

SYSTEM = """أنت مصمم ومؤلف «إنتاج معرفي» تعليمي. لغة المنتج يحددها صراحةً بند «لغة المنتج المعتمدة» في نهاية هذه التعليمات.

ما الإنتاج المعرفي؟
تجربة تعليمية تطبيقية قصيرة تحوّل هدفًا واحدًا إلى مسار ذي معنى. قد تظهر في صورة كتيّب، ملف تفاعلي، رحلة محطات، تحدٍّ، تحقيق، خريطة مهارات، بطاقات، ورشة مصغرة، مختبر، أو مهمة تصنع منتجًا. الشكل مرن، لكن المنتج ليس مجموعة أسئلة منفصلة ولا قصة زخرفية؛ كل جزء يخدم الهدف، وكل إجابة تضيف أثرًا ظاهرًا إلى ناتج يتكوّن تدريجيًا.

يمكن أن تستلهم التجربة من ممارسات تعليمية متنوعة:
- مدخل بصري أو موقف قصير يثير الفضول ويوضح الغاية.
- إضاءة معرفية موجزة عند الحاجة، لا تعيد شرح الدرس كاملًا.
- محطات أو بطاقات أو تحديات متدرجة تجمع بين القراءة والتفكير والتطبيق.
- منظم بصري أو سجل أو خريطة أو نموذج يبنيه المتعلم أثناء التقدم.
- مهمة ختامية ذات تسليم واضح ومعايير تقويم، ثم مراجعة تكشف منطق الحل.

أمثلة توضح المبدأ، وليست قوالب يجب تقليدها:
- «أجنحة في الظلام: من المعادلة إلى الصورة»: كل كثيرة حدود يبسّطها المتعلم منحنى في GeoGebra، والمنحنيات معًا ترسم خفاشًا.
- «خلف الشاشة: من الأثر الرقمي إلى كشف الحادثة»: كل دليل يصنفه المتعلم بمفهوم أمني، والأدلة معًا تفسر الحادثة وتبني خطة الوقاية.

البنية الدلالية الثابتة لكل منتج:
تمهيد (سياق + هدف + طريقة العمل) ← مراحل متدرجة ← ناتج تراكمي ← مهمة نهائية (تسليم + معايير) ← مراجعة تكشف منطق الحل.

البنية الملزمة لكل مرحلة، بلا استثناء:
1. عنوان قصير يدل على موقعها في المسار.
2. مشهد أو توجيه أو نشاط تمهيدي موجز.
3. سؤال صريح واحد من بنك الأسئلة، يظهر للمتعلم ويجيب عنه؛ لا توجد مرحلة بلا سؤال.
4. أثر تنتجه الإجابة الصحيحة ويضاف إلى الناتج التراكمي.
5. تفسير يظهر في نسخة المراجعة بعد الحل.

آليات تراكم الإجابات المتاحة (ليست قوالب للشكل البصري):
- cipher: لكل اختيار حرف؛ حروف الإجابات الصحيحة بالترتيب تكوّن كلمة سر تلخص غاية الموضوع. يناسب أهداف التمييز والتصنيف.
- case_file: كل مرحلة دليل يدوّن المتعلم علامته في سجل؛ السجل يقود إلى حكم. يناسب أهداف التحليل والتقويم.
- blueprint: كل مرحلة تكسب قطعة توضع في طبقة من مخطط؛ الطبقات معًا تكوّن بناءً مكتملًا. يناسب أهداف التطبيق والإنتاج.

قواعد ملزمة:
1. ابدأ من الهدف والجمهور والمفاهيم، ثم اختر سياقًا وشكل تجربة يخدمانها؛ لا تبدأ بزينة أو قالب جاهز.
2. انقل المفهوم ولا تُعِد الدرس: احتفظ بالمفاهيم الصحيحة وغيّر الغاية التي يستخدمها المتعلم من أجلها.
3. اجعل المسار متماسكًا ومتدرجًا: فهم أو ملاحظة ← اختيار أو تحليل ← تطبيق أو بناء ← تسليم نهائي.
4. السؤال إلزامي في كل مرحلة. استخدم question_ref من بنك الأسئلة مرة واحدة كما هو؛ لا تكتب سؤالًا جديدًا ولا تغيّر معناه أو ترتيب خياراته، وترجمه ترجمة أمينة فقط عندما تختلف لغته عن لغة المنتج؛ ولا تستبدله بنشاط أو قصة أو رابط.
5. المشهد يمهّد للسؤال ولا يكشف إجابته. النشاط المصاحب قصير وقابل للتنفيذ، لكنه لا يلغي السؤال.
6. يجب أن تغيّر كل إجابة شيئًا يمكن للمتعلم رؤيته أو تدوينه في الناتج؛ تجنب النقاط والشارات التي لا تخدم معنى المنتج.
7. نوّع التجربة داخل المنتج دون تشتيت: تعليمات واضحة، نص قليل، وتسلسل يمكن تنفيذه مطبوعًا أو على الشاشة من دون اعتماد على رابط خارجي.
8. العنوان عام صالح للتسجيل: لا تذكر صفًا ولا مرحلة دراسية ولا مدرسة ولا «مهمة أدائية» ولا «قدرات». العنوان الفرعي على نمط «من … إلى …».
9. لغة سليمة ملائمة للعمر وفق لغة المنتج المعتمدة، بجمل قصيرة وأفعال مباشرة، ومن دون حشو أو ادعاءات غير موجودة في محتوى الدرس.
10. كل الأمثلة مصطنعة وآمنة: لا روابط ولا رموز QR ولا أرقام هواتف ولا أسماء أشخاص أو جهات حقيقية.
11. التزم بمخطط JSON المطلوب حرفيًا؛ الحقل غير المستخدم في آلية التراكم قيمته null.
"""

ARCH_AR = {"cipher": "كلمة السر (cipher)", "case_file": "سجل الأدلة (case_file)", "blueprint": "المخطط ذو الطبقات (blueprint)"}
ARCH_EN = {"cipher": "cipher (secret word)", "case_file": "case_file (evidence log)", "blueprint": "blueprint (layered map)"}
ARCH_NAME = {"ar": ARCH_AR, "en": ARCH_EN}

# The lesson's language decides the language of EVERY generated value. The
# summary is a meaning reference only — an English lesson produces an English
# product even when its summary is Arabic.
LANG_RULE = {
    "ar": "لغة المنتج المعتمدة: العربية الفصحى، وكل حقل نصي في النتيجة يُكتب عربيًا.",
    "en": ("لغة المنتج المعتمدة: الإنجليزية. هذا الدرس درسٌ إنجليزي: اكتب كل حقل نصي في النتيجة "
           "بالإنجليزية — العناوين والعنوان الفرعي والقصة والقواعد والمشاهد والتفسيرات والمفاهيم "
           "والجداول ومعايير التقويم وكلمات الناتج وحقول التسجيل. ملخص الدرس العربي مرجع للمعنى فقط؛ "
           "لا تكتب أي كلمة عربية ولا رقمًا عربيًا-هنديًا في أي قيمة. "
           "وباقي الحقول النصية: question_text و choices و answer_text هي نص السؤال وخياراته وإجابته "
           "بلغة المنتج — عند اختلاف لغة سؤال البنك قدّم ترجمة أمينة بنفس المعنى ونفس ترتيب الخيارات "
           "وليست إعادة صياغة، وعند تطابق اللغة انسخها حرفيًا."),
}
KIND_LINE = {"ar": "«إنتاج معرفي تطبيقي في {subject}»",
             "en": "“Applied knowledge production in {subject}”"}
STAGE_LABEL = {"ar": "كلمة مفردة تناسب القصة (البطاقة، الدليل، المحطة، …)",
               "en": "a single English word that fits the story (Card, Clue, Stop, …)"}
SUBTITLE = {"ar": "على نمط: من … إلى …", "en": "on the pattern: from … to …"}
CIPHER_RULE = {
    "ar": ("payoff.solution كلمة عربية واحدة بلا تشكيل ولا مسافات، عدد حروفها {n} بالضبط "
           "(احسبها حرفًا حرفًا؛ التاء المربوطة حرف)، تلخص غاية الموضوع. payoff.meaning جملة تشرحها. "
           "columns و verdict و layers = null."),
    "en": ("payoff.solution ONE single English word, no spaces, exactly {n} letters "
           "(count them letter by letter), summarizing the topic's purpose. payoff.meaning one sentence explaining it. "
           "columns, verdict and layers = null."),
}
CASE_RULE = {
    "ar": ("payoff.columns ثلاثة أعمدة: [«{label}»، «قراري»، «العلامة التي لاحظتها»] أو ما يماثلها. "
           "payoff.verdict الحكم الذي تقود إليه الأدلة. solution و meaning و layers = null."),
    "en": ("payoff.columns three columns: [“{label}”, “My decision”, “What I noticed”] or equivalent. "
           "payoff.verdict the conclusion the evidence leads to. solution, meaning and layers = null."),
}
LAYER_RULE = {
    "ar": ("payoff.layers من طبقتين إلى ثلاث، كل عنوان بصيغة «الطبقة الأولى: …». "
           "solution و meaning و columns و verdict = null."),
    "en": ("payoff.layers two to three layers, each titled as “Layer 1: …”. "
           "solution, meaning, columns and verdict = null."),
}
LINK_RULE = {
    "ar": {
        "cipher": "finding و component و layer = null.",
        "case_file": "finding: العلامة التي يدوّنها المتعلم في السجل بعد الإجابة الصحيحة (عبارة قصيرة). component و layer = null.",
        "blueprint": ("component: القطعة المكتسبة بعبارة قصيرة تبدأ باسم أو فعل. layer: أحد العناوين الآتية حرفيًا، "
                      "وكل طبقة تحصل على قطعة واحدة على الأقل: {layers}. finding = null."),
    },
    "en": {
        "cipher": "finding, component and layer = null.",
        "case_file": "finding: the mark the learner records in the log after the correct answer (a short phrase). component and layer = null.",
        "blueprint": ("component: the piece earned, as a short phrase starting with a noun or verb. layer: one of the following titles, "
                      "verbatim, and every layer gets at least one piece: {layers}. finding = null."),
    },
}
LINK_LANG = {
    "ar": ("- question_text: نص السؤال بلغة المنتج — ترجمة أمينة عند اختلاف اللغة (نفس المعنى ونفس ترتيب الخيارات)، وإلا النص كما هو.\n"
           "- choices: خيارات multiple_choice بنفس الترتيب بلغة المنتج؛ ولغيره null.\n"
           "- answer_text: الإجابة بلغة المنتج للإكمال والإجابة القصيرة؛ وللصحيح/الخطأ والاختيار من متعدد null.\n"),
    "en": ("- question_text: the bank question in the product's language — a faithful translation when the bank is in another language (same meaning, same option order), otherwise verbatim.\n"
           "- choices: the multiple_choice options in the same order, in the product's language; null for other kinds.\n"
           "- answer_text: the answer in the product's language for complete and short_answer; null for true_false and multiple_choice (derived).\n"),
}


def _j(o):
    return json.dumps(o, ensure_ascii=False, indent=1)


def base(content, title, lang="ar"):
    return [{"role": "system", "content": SYSTEM + "\n\n" + LANG_RULE.get(lang, LANG_RULE["ar"])},
            {"role": "user", "content": f"ملخص الدرس المعتمد من قاعدة بيانات AI «{title}»:\n\n{content}"}]


# ------------------------------------------------------------------ step A
def topics(goals, subject, lang="ar"):
    """Goals include the worksheet text and the safe question candidates."""
    return ("المطلوب الآن: حوّل كل هدف في ورقة العمل إلى موضوع إنتاج معرفي مستقل، ثم اختر له أسئلة البنك الأكثر ارتباطًا.\n\n"
            f"الأهداف وأسئلة البنك المسموح بها لكل هدف:\n{_j(goals)}\n\n"
            "التعليمات:\n"
            "- موضوع واحد لكل هدف، و goal_id كما هو تمامًا.\n"
            "- أعد صياغة معنى الهدف في title كعنوان إنتاج معرفي قصير وجذاب؛ لا تنسخ جملة الهدف كما هي.\n"
            "- question_refs: اختر فقط معرّفات من questions داخل الهدف نفسه، بلا تكرار، وبعدد بين min_questions و max_questions. اختر الأسئلة الأقرب دلاليًا إلى الموضوع والتي تتكامل لتغطيه؛ سيُعاد توظيف كل سؤال تختاره في مرحلة أو في المهمة النهائية.\n"
            "- لا تختر cipher إلا إذا كان في الأسئلة المختارة أربعة أسئلة gradable على الأقل.\n"
            "- اختر آلية تراكم تناسب المستوى المعرفي، ثم ابتكر شكل تجربة مناسبًا داخل premise؛ لا تجعل الآلية هي الفكرة نفسها.\n"
            "- نوّع أشكال التجربة بين الموضوعات (مسار، تحدٍّ، خريطة، ورشة، بطاقات، تحقيق، بناء...) ونوّع آليات التراكم قدر الإمكان، ولا تكرر عنوانًا.\n"
            f"- stage_label {STAGE_LABEL[lang]}.\n"
            f"- kind_line: {KIND_LINE[lang].format(subject=subject)}.\n"
            f"- subtitle {SUBTITLE[lang]}.\n"
            "- premise يصف ما يراه المتعلم وما يفعله من البداية إلى التسليم، لا مجرد قصة عامة.\n"
            "- ابنِ الفكرة على ملخص الدرس المعتمد أعلاه، لا على معرفة عامة منفصلة عنه.\n"
            "- concept_transfer يربط مفاهيم الهدف بكل مرحلة، ويؤكد أن لكل مرحلة سؤال بنك ظاهرًا، ويوضح كيف تنتج الإجابات الناتج النهائي.")


# ------------------------------------------------------------------ step B
def project(goal, topic, n_stages, n_open, lang="ar"):
    arch = topic["archetype"]
    rule = {
        "cipher": CIPHER_RULE[lang].format(n=n_stages),
        "case_file": CASE_RULE[lang].format(label=topic["stage_label"]),
        "blueprint": LAYER_RULE[lang],
    }[arch]
    return (f"المطلوب الآن: اكتب مشروع الإنتاج المعرفي كاملًا لهذا الموضوع.\n\n"
            f"الهدف: {goal['text']}\n\nالموضوع:\n{_j(topic)}\n\n"
            f"سيحتوي المنتج على {n_stages} مراحل؛ في كل مرحلة مساحة سؤال ظاهرة ومرتبطة بسؤال واحد من البنك، و{n_open} سؤال مفتوح في المهمة النهائية. "
            "لا تكتب الأسئلة الآن.\n\n"
            "التعليمات:\n"
            "- intro.story فقرتان أو ثلاث تقدمان السياق والغاية ومسار العمل بلغة عملية، من دون تضخيم القصة. intro.rules من 3 إلى 5 قواعد.\n"
            "- صمّم المراحل ذهنيًا كتتابع متنوع من تمهيد أو إضاءة أو ملاحظة أو تطبيق قصير، لكن السؤال الصريح يظل عنصرًا إلزاميًا في كل مرحلة. لا تضع روابط أو مهامًا تعتمد على مصدر خارجي.\n"
            f"- الناتج نمط {ARCH_NAME[lang][arch]}: {rule}\n"
            "- final_task.deliverable جدول من 2 إلى 4 أعمدة و3 صفوف؛ rows قيمة العمود الأول أو نص فارغ، "
            "و model الصفوف مكتملة بعرض الأعمدة نفسه.\n"
            "- final_task.prompt يطلب منتجًا أصيلًا يمكن مراجعته، ويستفيد من آثار إجابات المراحل بدل تكرارها. final_task.rubric ثلاثة معايير محددة وقابلة للملاحظة.\n"
            "- reveal.story يشرح كيف أنتجت الإجابات الناتج ويربطه بالهدف؛ reference تعريفات موجزة للمفاهيم؛ plan من 3 إلى 5 إجراءات تطبيقية.\n"
            "- لا تجعل أي جزء بديلًا عن سؤال المرحلة: القصة والنشاط والناتج تخدم السؤال وتبني عليه.")


# ------------------------------------------------------------------ step C
def link(topic, project_, questions, n_stages, lang="ar"):
    arch = topic["archetype"]
    rule = LINK_RULE[lang][arch].format(layers=_j(project_["payoff"].get("layers"))) if arch == "blueprint" else LINK_RULE[lang][arch]
    return (f"المطلوب الآن: اربط أسئلة البنك بمراحل المنتج «{topic['title']}».\n\n"
            f"الناتج:\n{_j(project_['payoff'])}\n\nالأسئلة المتاحة:\n{_j(questions)}\n\n"
            "التعليمات:\n"
            f"- أعد {n_stages} مراحل بالضبط. كل مرحلة لها question_ref غير فارغ يُختار فقط من سؤال stage_eligible=true، وكل سؤال يستخدم مرة واحدة فقط.\n"
            "- أعد final_questions لكل سؤال متاح لم تستخدمه المراحل، مرة واحدة وبالترتيب الوارد. question_text و choices و answer_text كلها بلغة المنتج.\n"
            "- في final_questions: choices مطلوبة فقط للاختيار من متعدد وبنفس الترتيب، وإلا null. answer_text هو الجواب النموذجي المترجم؛ وللصحيح/الخطأ استخدم علامة لغة المنتج (ص/خ أو T/F).\n"
            "- سؤال البنك هو التفاعل الأساسي في المرحلة وسيظهر بنصه وخياراته في المنتج النهائي؛ لا توجد حالة يجوز فيها حذف السؤال أو استبداله بنشاط أو تعليمات أو رابط.\n"
            "- رتّب المراحل بما يبني القصة. title عنوان قصير للمرحلة.\n"
            "- scene جملة أو جملتان تقدمان موقفًا أو ملاحظة أو إجراءً قصيرًا يقود مباشرة إلى السؤال، دون إعادة صياغة السؤال أو ذكر الإجابة.\n"
            "- explanation جملة واحدة دقيقة تفسر الإجابة الصحيحة بعد الحل وتربطها بالمفهوم.\n"
            "- لأسئلة الإكمال (complete): word_bank كلمتان خاطئتان معقولتان من الحقل نفسه؛ ولغيرها null.\n"
            + LINK_LANG[lang]
            + f"- {rule}")


def repair(errors):
    return ("النتيجة السابقة لم تجتز الفحص. أعد النتيجة كاملة بعد إصلاح هذه الأخطاء فقط:\n- "
            + "\n- ".join(errors))
