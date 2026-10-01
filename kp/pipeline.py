"""Entry point for goal-first production; legacy replay mechanics below remain for compatibility."""
import json
import re
from . import PROMPT_VERSION, SCHEMA_VERSION, prompts
from .models import Topics, Project, Link
from .bank import build_bank
from .assemble import assemble
from .validate import check_topics, check_project, check_product, cipher_letters, topic_warnings
from .store import find_questions_record, get_record, prepare_record, save_record
from .content import ContentNotFound
from .llm import LLMError


def _step(llm, step, base, task, schema, meta, check, max_repairs, counters, progress=None):
    if progress:
        progress(step, goal_id=meta.get("goal_id"), state="started")
        meta = {**meta, '_progress': progress}
    msgs = base + [{"role": "user", "content": task}]
    out = llm.complete(step, msgs, schema, meta)
    errors = check(out)
    while errors and counters.get(step, 0) < max_repairs:
        counters[step] = counters.get(step, 0) + 1
        if progress:
            progress(step, goal_id=meta.get("goal_id"), state="repair",
                     attempt=counters[step], errors=errors)
        msgs = msgs + [{"role": "assistant", "content": json.dumps(out, ensure_ascii=False)},
                       {"role": "user", "content": prompts.repair(errors)}]
        out = llm.complete(step, msgs, schema, meta)
        errors = check(out)
    if progress:
        progress(step, goal_id=meta.get("goal_id"), state="failed" if errors else "validated",
                 **({'errors': errors} if errors else {}))
    return out, errors


def _stage_plan(questions, archetype, s):
    """Which questions may become stages, and how many."""
    gradable = [q for q in questions if q.gradable]
    pool = gradable if (archetype == "cipher" or len(gradable) >= s.min_stages) else questions
    return pool, min(s.max_stages, len(pool))


def plan_lesson(doc, bank, s):
    """What a run would do — no model calls."""
    goals = []
    for g in bank.goals:
        candidates = bank.candidates_for(g)
        gradable = [q for q in candidates if q.gradable]
        goals.append({"goal_id": g.id, "questions": len(candidates), "gradable": len(gradable),
                      "cipher_possible": len(gradable) >= s.min_stages,
                      "ok": len(candidates) >= s.min_stages})
    runnable = sum(1 for g in goals if g["ok"])
    content_chars = min(len(doc.content), s.content_max_chars)
    return {"goals": goals, "calls": 1 + 2 * runnable,
            "rough_input_tokens": int((content_chars / 3 + 1500) * (1 + 2 * runnable)),
            "note": "rough: ~3 Arabic chars per token; repairs add calls; content prefix is cached after the first call"}


def generate_lesson(lesson_id, id_type, **kwargs):
    """New generation is goal-first; replay can still exercise legacy records."""
    if getattr(kwargs['llm'], 'legacy_archetypes', False):
        kwargs.pop('progress', None)
        return _generate_legacy_lesson(lesson_id, id_type, **kwargs)
    from .production import generate_lesson as generate_production
    return generate_production(lesson_id, id_type, **kwargs)


def _generate_legacy_lesson(lesson_id, id_type, *, content_src, db, llm, s, force=False, only_goals=None,
                    dry_run=False, store_record=True):
    res = {"lesson_id": str(lesson_id), "id_type": id_type}
    try:
        doc = content_src.get(lesson_id, id_type)
    except ContentNotFound as e:
        return {**res, "status": "no_content", "reason": str(e)}
    res.update(document_uuid=doc.uuid, document_idx=doc.idx, title=doc.title)
    if not doc.goals:
        return {**res, "status": "no_goals",
                "reason": f"no goals in ai.{s.col_worksheets} worksheet.goals"}

    qrec = find_questions_record(db, s.col_questions, doc)
    if not qrec:
        return {**res, "status": "no_questions",
                "reason": "no ai.questions record — run the existing generator first (main.py … questions)"}
    bank = build_bank(qrec, doc.goals)
    goals = [g for g in bank.goals if not only_goals or g.id in only_goals]
    if not goals:
        return {**res, "status": "no_goals", "reason": "the question record has no learning_goals"}

    existing = get_record(db, s.col_knowledge, doc.uuid)
    fresh = (existing and existing.get("bank_fingerprint") == bank.fingerprint
             and existing.get("content_fingerprint") == doc.fingerprint
             and existing.get("prompt_version") == PROMPT_VERSION)
    if fresh and not force and not only_goals and not existing.get("failed_goals"):
        return {**res, "status": "up_to_date", "products": len(existing.get("products", []))}
    if dry_run:
        return {**res, "status": "dry_run", "plan": plan_lesson(doc, bank, s),
                "existing": bool(existing), "stale": bool(existing and not fresh)}

    lang = doc.language
    subject = bank.subject or doc.title
    # Some English lessons were generated from Arabic metadata/summary records.
    # The lesson title and goals decide the language; do not let an Arabic bank
    # subject leak back into an otherwise English knowledge-production record.
    if lang == "en" and re.search(r"[\u0600-\u06FF]", subject or ""):
        subject = doc.title
    base = prompts.base(doc.content[: s.content_max_chars], doc.title, lang)
    counters, failed, products = {}, [], []

    candidate_by_goal = {g.id: bank.candidates_for(g) for g in goals}
    runnable = [g for g in goals if len(candidate_by_goal[g.id]) >= s.min_stages]
    for g in goals:
        if g not in runnable:
            failed.append({"goal_id": g.id, "reason": f"only {len(candidate_by_goal[g.id])} topic questions; {s.min_stages} needed"})
    try:
        # ---- A. goals → topics (one call, so topics can be told apart) -------
        max_topic_questions = s.max_stages + 3
        gmeta = []
        for g in runnable:
            candidates = candidate_by_goal[g.id]
            gmeta.append({
                "id": g.id,
                "text": g.text,
                "cognitive_level": g.cognitive_level,
                "min_questions": s.min_stages,
                "max_questions": min(max_topic_questions, len(candidates)),
                "questions": [q.for_prompt() | {"gradable": q.gradable} for q in candidates],
            })
        if runnable:
            topics_out, errs = _step(llm, "topics", base, prompts.topics(gmeta, subject, lang), Topics,
                                     {"goals": gmeta, "subject": subject, "language": lang},
                                     lambda o: check_topics(o["topics"], runnable, candidate_by_goal,
                                                            s.min_stages, max_topic_questions, lang=lang),
                                     s.max_repairs, counters)
            if errs:
                return {**res, "status": "failed", "reason": "topics", "errors": errs, "usage": llm.usage.as_dict(s)}
            topic_by_goal = {t["goal_id"]: t for t in topics_out["topics"]}

        for g in runnable:
            topic = topic_by_goal[g.id]
            selected = [bank.index[ref] for ref in topic["question_refs"]]
            pool, n_pool = _stage_plan(selected, topic["archetype"], s)
            # ---- B. project ---------------------------------------------------
            project, errs = _step(llm, "project", base, prompts.project({"text": g.text}, topic, n_pool, len(selected) - n_pool, lang),
                                  Project, {"goal_id": g.id, "goal_text": g.text, "topic": topic,
                                            "language": lang},
                                  lambda o: check_project(o, topic, len([q for q in selected if q.gradable]),
                                                          s.min_stages, n_pool, lang=lang),
                                  s.max_repairs, counters)
            if errs:
                failed.append({"goal_id": g.id, "reason": "project: " + " | ".join(errs)}); continue
            n = len(cipher_letters(project["payoff"]["solution"])) if topic["archetype"] == "cipher" else n_pool
            stage_ids = {q.id for q in pool}
            questions = [q.for_prompt() | {"stage_eligible": q.id in stage_ids} for q in selected]

            # ---- C. link questions → stages, assembled and checked as stored ---
            holder = {}

            def check_link(out, g=g, topic=topic, project=project, n=n):
                holder["product"] = assemble(doc, g, topic, project, out, bank, selected, s.edition_year)
                errs, warns = check_product(holder["product"], bank, expected_stages=n,
                                            allowed_refs={q.id for q in selected}, lang=lang)
                holder["warnings"] = warns
                return errs

            _, errs = _step(llm, "link", base, prompts.link(topic, project, questions, n, lang), Link,
                            {"goal_id": g.id, "topic": topic, "project": project, "questions": questions,
                             "n_stages": n, "language": lang},
                            check_link, s.max_repairs, counters)
            if errs:
                failed.append({"goal_id": g.id, "reason": "link: " + " | ".join(errs)}); continue
            product = holder["product"]
            product["review"] = {"status": "pending", "warnings": holder["warnings"] + topic_warnings(topic, lang),
                                 "reviewed_by": None, "reviewed_at": None}
            products.append(product)
    except LLMError as e:
        return {**res, "status": "failed", "reason": str(e), "usage": llm.usage.as_dict(s)}

    regenerated = [p["goal_id"] for p in products]
    # A partial re-run keeps the other goals' products if the bank did not change.
    if only_goals and fresh:
        keep = [p for p in existing.get("products", []) if p["goal_id"] not in {g.id for g in goals}]
        products = sorted(keep + products, key=lambda p: [g.id for g in bank.goals].index(p["goal_id"]))

    if not products:
        return {**res, "status": "failed", "failed_goals": failed, "usage": llm.usage.as_dict(s)}

    record = {
        "schema_version": SCHEMA_VERSION, "kind": "knowledge_production",
        "document_uuid": doc.uuid or qrec.get("document_uuid"),
        "document_idx": str(qrec.get("document_idx") or doc.idx),
        "custom_id": doc.custom_id or qrec.get("custom_id") or None,
        "filename": doc.title or qrec.get("filename") or "", "subject": subject or None,
        "language": doc.language,
        "bank_fingerprint": bank.fingerprint, "content_fingerprint": doc.fingerprint,
        "prompt_version": PROMPT_VERSION,
        "generation": {"llm": llm.name, "unit": "one_product_per_worksheet_goal",
                       "content_source": "ai.summaries", "goal_source": "ai.worksheets",
                       "question_policy": "select_and_reuse",
                       "usage": {**llm.usage.as_dict(s), "repairs": counters}, "requires_human_review": True},
        "products": products, "failed_goals": failed,
    }
    record = save_record(db, s.col_knowledge, record) if store_record else prepare_record(record)
    return {**res, "status": "partial" if failed else "generated", "products": len(products), "regenerated": regenerated,
            "failed_goals": failed, "repairs": counters, "usage": llm.usage.as_dict(s),
            **({"_record": record} if not store_record else {})}
