"""Checks, split by the step that can fix them.

check_topics   → repaired by re-running step A
check_project  → repaired by re-running step B
check_product  → repaired by re-running step C (the assembled, storable product)

Every message is written to be handed back to the model verbatim, so it names
the field and says what is expected.
"""
import re

ARCHETYPES = {"cipher", "case_file", "blueprint"}
TF = ["صح", "خطأ"]
# From the attached registration guide: general titles avoid a Ministry / Qiyas
# approval step. A mirror of that guide, not a check of current official rules.
TITLE_FORBIDDEN = ["الصف", "ابتدائي", "متوسط", "ثانوي", "مدرسة", "مهمة أدائية", "المهمة الأدائية",
                   "القدرات", "الفصل الدراسي", "الوحدة"]
NOT_LETTER = re.compile(r"[\u064B-\u0652\u0670\u0640\s]")   # tashkeel, tatweel, spaces


def cipher_letters(word):
    return list(NOT_LETTER.sub("", word or ""))


_ARABIC_RUN = re.compile(r"[\u0600-\u06FF]")
_LANG_SKIP = {"goal_text", "question_ref", "question_refs", "id", "goal_id", "mode", "review"}


def lang_errors(node, where="product"):
    """Arabic script anywhere in an English product is a repairable error:
    every word of the stored files must be in the lesson's own language."""
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k not in _LANG_SKIP:
                out += lang_errors(v, f"{where}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out += lang_errors(v, f"{where}[{i}]")
    elif isinstance(node, str) and _ARABIC_RUN.search(node):
        out.append(f"{where}: «{node[:40]}» يحتوي حروفًا عربية؛ لغة هذا الدرس الإنجليزية فكل الكلمات إنجليزية.")
    return out


def _title_errors(where, title, subtitle):
    out = []
    for bad in TITLE_FORBIDDEN:
        if bad in f"{title} {subtitle}":
            out.append(f"{where}: العنوان يحتوي «{bad}»؛ يجب أن يكون العنوان عامًا بلا صف أو مرحلة أو مدرسة.")
    return out


# ---------------------------------------------------------------- step A
def check_topics(topics, goals, candidate_questions, min_stages, max_questions, lang="ar"):
    errors, by_goal = [], {}
    for t in topics:
        by_goal.setdefault(t["goal_id"], []).append(t)
    for g in goals:
        n = len(by_goal.get(g.id, []))
        if n != 1:
            errors.append(f"الهدف {g.id}: يجب موضوع واحد بالضبط، ووُجد {n}.")
    for gid in by_goal:
        if gid not in {g.id for g in goals}:
            errors.append(f"goal_id «{gid}» غير موجود في قائمة الأهداف.")
    gmap = {g.id: g for g in goals}
    titles = [t["title"] for t in topics]
    for t in topics:
        where = f"الموضوع {t['goal_id']}"
        errors += _title_errors(where, t["title"], t["subtitle"])
        goal = gmap.get(t["goal_id"])
        if goal and " ".join(t["title"].split()).rstrip(".؟") == " ".join(goal.text.split()).rstrip(".؟"):
            errors.append(f"{where}: title ينسخ نص الهدف كما هو؛ أعد صياغته عنوانًا قصيرًا للإنتاج المعرفي.")
        refs = t.get("question_refs") or []
        allowed_questions = {q.id: q for q in candidate_questions.get(t["goal_id"], [])}
        allowed = set(allowed_questions)
        if len(refs) != len(set(refs)):
            errors.append(f"{where}: question_refs تحتوي سؤالًا مكررًا.")
        unknown = [ref for ref in refs if ref not in allowed]
        if unknown:
            errors.append(f"{where}: question_refs غير مسموحة لهذا الهدف: {unknown}.")
        upper = min(max_questions, len(allowed))
        if not min_stages <= len(refs) <= upper:
            errors.append(f"{where}: اختر من {min_stages} إلى {upper} أسئلة، واختير {len(refs)}.")
        selected_gradable = sum(1 for ref in refs if ref in allowed_questions and allowed_questions[ref].gradable)
        if t["archetype"] == "cipher" and selected_gradable < min_stages:
            errors.append(f"{where}: cipher يحتاج {min_stages} أسئلة قابلة للتصحيح على الأقل، والمتاح "
                          f"{selected_gradable}؛ اختر case_file أو blueprint.")
        stageable = selected_gradable if selected_gradable >= min_stages else len(refs)
        if len(refs) - min(max_questions - 3, stageable) > 3:
            errors.append(f"{where}: عدّل question_refs حتى يُعاد توظيف كل سؤال مختار في مرحلة أو المهمة النهائية.")
        if titles.count(t["title"]) > 1:
            errors.append(f"{where}: العنوان «{t['title']}» مكرر؛ اجعل لكل موضوع عنوانًا مختلفًا.")
        if len(t["premise"]) < 40 or len(t["concept_transfer"]) < 40:
            errors.append(f"{where}: premise و concept_transfer يجب أن يكونا جملتين كاملتين على الأقل.")
        if lang == "en":
            errors += lang_errors({k: v for k, v in t.items() if k not in _LANG_SKIP}, where)
    return errors


def topic_warnings(topic, lang="ar"):
    w = []
    if lang == "en":
        if not re.match(r"(?i)^from .+ to .+", topic["subtitle"]):
            w.append("subtitle does not follow the «from … to …» pattern")
    elif not re.match(r"^من .+ إلى .+", topic["subtitle"]):
        w.append("العنوان الفرعي لا يتبع نمط «من … إلى …»")
    return w


# ---------------------------------------------------------------- step B
def check_project(project, topic, n_gradable, min_stages, expected_stages=None, lang="ar"):
    e, p, arch = [], project["payoff"], topic["archetype"]
    if arch == "cipher":
        letters = cipher_letters(p.get("solution"))
        if expected_stages is not None and len(letters) != expected_stages:
            e.append(f"payoff.solution «{p.get('solution')}» فيها {len(letters)} حروف؛ المطلوب {expected_stages} بالضبط.")
        elif not (min_stages <= len(letters) <= n_gradable):
            e.append(f"payoff.solution «{p.get('solution')}» فيها {len(letters)} حروف؛ المطلوب بين {min_stages} و {n_gradable}.")
        if not p.get("meaning"):
            e.append("payoff.meaning مطلوب في cipher.")
    elif arch == "case_file":
        if not p.get("columns") or len(p["columns"]) < 2:
            e.append("payoff.columns مطلوبة في case_file (عمودان على الأقل).")
        if not p.get("verdict"):
            e.append("payoff.verdict مطلوب في case_file.")
    elif arch == "blueprint":
        layers = p.get("layers") or []
        if not 2 <= len(layers) <= 4 or len(set(layers)) != len(layers):
            e.append("payoff.layers يجب أن تكون من 2 إلى 4 عناوين مختلفة.")
    d = project["final_task"]["deliverable"]
    if not 2 <= len(d["columns"]) <= 4:
        e.append("final_task.deliverable.columns يجب أن تكون من 2 إلى 4.")
    if any(len(r) != len(d["columns"]) for r in d["model"]):
        e.append("كل صف في final_task.deliverable.model يجب أن يكون بعدد الأعمدة نفسه.")
    if len(project["final_task"]["rubric"]) < 2:
        e.append("final_task.rubric يحتاج معيارين على الأقل.")
    if len(project["intro"]["story"]) < 1 or len(project["intro"]["rules"]) < 2:
        e.append("intro يحتاج قصة وقاعدتين على الأقل.")
    if len(project["reveal"]["story"]) < 60:
        e.append("reveal.story قصير جدًا؛ اشرح كيف أنتجت الإجابات الناتج.")
    if lang == "en":
        e += lang_errors(project)
    return e


# ---------------------------------------------------------------- step C (+ assembly)
def check_product(product, bank, expected_stages=None, allowed_refs=None, lang="ar"):
    """The storable product, checked against the bank it references."""
    e, w = [], []
    gid, arch = product["goal_id"], product["idea"]["archetype"]
    payoff, stages = product["payoff"], product["stages"]
    if arch not in ARCHETYPES or payoff.get("type") != arch:
        e.append("idea.archetype و payoff.type غير متطابقين.")
    if expected_stages is not None and len(stages) != expected_stages:
        e.append(f"المطلوب {expected_stages} مراحل بالضبط، ووُجد {len(stages)}.")
    used, solved = set(), []
    for s in stages:
        ref, y = s.get("question_ref"), s.get("yields", {})
        at = f"المرحلة {s.get('n')}"
        if not isinstance(ref, str) or not ref.strip():
            e.append(f"{at}: question_ref مطلوب؛ لا يجوز إنشاء مرحلة بلا سؤال من بنك الأسئلة.")
            continue
        q = bank.index.get(ref)
        if not q:
            e.append(f"{at}: question_ref «{ref}» غير موجود في القائمة."); continue
        if allowed_refs is not None and ref not in allowed_refs:
            e.append(f"{at}: السؤال {ref} لم يُختر لهذا الموضوع.")
        if q.goal_id and q.goal_id != gid:
            e.append(f"{at}: السؤال {ref} يخص {q.goal_id} لا {gid}.")
        if ref in used:
            e.append(f"{at}: السؤال {ref} مستخدم مرتين.")
        used.add(ref)
        ans = s.get("answer_text") or q.answer_text
        if ans and len(ans) > 3 and ans in s.get("scene", ""):
            e.append(f"{at}: المشهد يذكر الإجابة «{ans}»؛ أعد كتابته دون كشفها.")
        if arch == "cipher":
            if not q.gradable:
                e.append(f"{at}: السؤال {ref} غير قابل للتصحيح الآلي، ولا يصلح لكلمة السر."); continue
            choices = s.get("choices") or (q.choices if q.kind == "multiple_choice" else TF if q.kind == "true_false" else y.get("bank") or [])
            tokens = y.get("tokens") or []
            if len(tokens) != len(choices) or ans not in choices:
                e.append(f"{at}: الحروف لا تطابق الخيارات."); continue
            right = tokens[choices.index(ans)]
            if tokens.count(right) > 1:
                e.append(f"{at}: خيار خاطئ يحمل حرف الإجابة الصحيحة.")
            solved.append(right)
        elif arch == "case_file" and not y.get("finding"):
            e.append(f"{at}: finding مطلوب في case_file.")
        elif arch == "blueprint":
            if not y.get("component"):
                e.append(f"{at}: component مطلوب في blueprint.")
            if y.get("layer") not in (payoff.get("layers") or []):
                e.append(f"{at}: layer «{y.get('layer')}» ليس من عناوين الطبقات {payoff.get('layers')}.")
        if q.kind == "complete" and y.get("bank") and ans not in y["bank"]:
            e.append(f"{at}: بنك الكلمات لا يحتوي الإجابة «{ans}».")
    if arch == "cipher" and "".join(solved) != "".join(cipher_letters(payoff.get("solution"))):
        e.append(f"الناتج معطوب: الإجابات الصحيحة تكوّن «{''.join(solved)}» لا «{payoff.get('solution')}».")
    if arch == "blueprint":
        for layer in payoff.get("layers") or []:
            if not any(s.get("yields", {}).get("layer") == layer for s in stages):
                e.append(f"الطبقة «{layer}» لم تحصل على أي قطعة؛ وزّع المراحل على كل الطبقات.")
    final_task = product["final_task"]
    final_refs = final_task.get("question_refs", [])
    final_items = final_task.get("questions", [])
    item_refs = [item.get("question_ref") for item in final_items]
    if item_refs != final_refs:
        e.append(f"المهمة النهائية: questions يجب أن تطابق question_refs بالترتيب؛ وُجد {item_refs} بدل {final_refs}.")
    for item in final_items:
        ref = item.get("question_ref")
        q = bank.index.get(ref)
        where = f"المهمة النهائية {ref}"
        if not item.get("question_text"):
            e.append(f"{where}: question_text مطلوب بلغة المنتج.")
        if not item.get("answer_text"):
            e.append(f"{where}: answer_text مطلوب بلغة المنتج.")
        choices = item.get("choices")
        if q and q.kind == "multiple_choice" and (not isinstance(choices, list) or len(choices) != len(q.choices)):
            e.append(f"{where}: choices يجب أن تطابق عدد خيارات سؤال البنك وترتيبها.")
    for ref in final_refs:
        q = bank.index.get(ref)
        if not q or (q.goal_id and q.goal_id != gid) or (allowed_refs is not None and ref not in allowed_refs):
            e.append(f"المهمة النهائية: السؤال {ref} غير صالح لهذا الهدف.")
        elif ref in used:
            e.append(f"المهمة النهائية: السؤال {ref} مستخدم في مرحلة.")
    e += _title_errors("الموضوع", product["idea"]["title"], product["idea"]["subtitle"])
    w += topic_warnings(product["idea"], lang)
    if lang == "en":
        e += lang_errors(product)
    return e, w
