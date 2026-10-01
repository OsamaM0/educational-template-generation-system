"""Generalized KP generation; legacy booklet records remain supported separately."""
import re
from pymongo.errors import PyMongoError
from . import PROMPT_VERSION, SCHEMA_VERSION
from . import production_prompts as prompts
from .production_models import ProductionTopics, ProductionProject, ProductionLinks
from .production_validate import check_topics, check_project, check_links, normalize_empty_fields
from .bank import build_bank
from .content import ContentNotFound
from .store import find_questions_record, get_record, prepare_record, save_record
from .llm import LLMError
from .assemble import REGISTRATION
from .pending import write_pending


def generate_lesson(lesson_id, id_type, *, content_src, db, llm, s, force=False,
                    only_goals=None, dry_run=False, store_record=True, progress=None):
    from .pipeline import _step
    res = {'lesson_id': str(lesson_id), 'id_type': id_type}
    if progress:
        progress('load_content', state='started')
    try:
        doc = content_src.get(lesson_id, id_type)
    except ContentNotFound as e:
        return {**res, 'status':'no_content', 'reason':str(e)}
    res.update(document_uuid=doc.uuid, document_idx=doc.idx, title=doc.title)
    if progress:
        progress('load_content', state='completed', title=doc.title)
    if not doc.goals:
        return {**res, 'status':'no_goals', 'reason':f'no goals in ai.{s.col_worksheets} worksheet.goals'}
    qrec = find_questions_record(db, s.col_questions, doc) or {}
    bank = build_bank(qrec, doc.goals)
    goals = [g for g in bank.goals if not only_goals or g.id in only_goals]
    if not goals:
        return {**res, 'status':'no_goals', 'reason':'No matching worksheet goals.'}
    if progress:
        progress('plan', state='completed', total_goals=len(goals))
    existing = get_record(db, s.col_knowledge, doc.uuid)
    fresh = bool(existing and existing.get('bank_fingerprint') == bank.fingerprint
                 and existing.get('content_fingerprint') == doc.fingerprint
                 and existing.get('prompt_version') == PROMPT_VERSION
                 and all('sections' in p for p in existing.get('products', [])))
    if only_goals and existing and not fresh:
        return {**res, 'status':'failed',
                'reason':'Stored production is stale. Run without --goals to regenerate the whole lesson safely.'}
    if fresh and existing.get('failed_goals') and not force and not only_goals:
        retry_ids = {item['goal_id'] for item in existing['failed_goals']}
        retry_goals = [g for g in bank.goals if g.id in retry_ids]
        if retry_goals:
            only_goals = retry_ids
            goals = retry_goals
            if progress:
                progress('plan', state='retry_failed_goals', total_goals=len(goals),
                         goal_ids=[g.id for g in goals])
    covered = {p['goal_id'] for p in (existing or {}).get('products', [])}
    if (fresh and not force and not only_goals and not existing.get('failed_goals')
            and covered == {g.id for g in bank.goals}):
        return {**res, 'status':'up_to_date', 'products':len(existing['products'])}
    candidates = {g.id:bank.candidates_for(g) for g in goals}
    if dry_run:
        calls = 1 + len(goals) + sum(bool(candidates[g.id]) for g in goals)
        return {**res, 'status':'dry_run', 'existing':bool(existing), 'stale':bool(existing and not fresh),
                'plan':{'goals':[{'goal_id':g.id,'questions':len(candidates[g.id]),'ok':True} for g in goals],
                        'calls':calls, 'note':'Upper bound before optional question selection; no questions are required.'}}
    lang = doc.language
    subject = bank.subject or doc.title
    if lang == 'en' and re.search(r'[\u0600-\u06ff]', subject):
        subject = doc.title
    base = prompts.base(doc.content[:s.content_max_chars], doc.title, lang)
    limit = s.max_questions
    gmeta = [{'id':g.id,'text':g.text,'cognitive_level':g.cognitive_level,
              'max_questions':limit,'questions':[q.for_prompt() for q in candidates[g.id]]} for g in goals]
    counters, failed, products = {}, [], []
    try:
        topics, errors = _step(llm, 'topics', base, prompts.topics(gmeta, subject), ProductionTopics,
                               {'goals':gmeta,'subject':subject,'language':lang,'generalized':True},
                               lambda o:check_topics(o, goals, candidates, limit, lang), s.max_repairs, counters, progress)
    except LLMError as e:
        return {**res,'status':'failed','reason':str(e),'usage':llm.usage.as_dict(s)}
    if errors:
        return {**res,'status':'failed','reason':'topics','errors':errors,'usage':llm.usage.as_dict(s)}
    by_goal = {t['goal_id']:t for t in topics['topics']}
    for number, goal in enumerate(goals, 1):
        topic = by_goal[goal.id]
        selected = [bank.index[ref] for ref in topic['question_refs']]
        qmeta = [q.for_prompt() for q in selected]
        local = {}  # a repair budget per goal, not shared by all products
        try:
            project, errors = _step(llm, 'project', base, prompts.project(goal.text, topic, qmeta), ProductionProject,
                                   {'goal_id':goal.id,'goal_text':goal.text,'topic':topic,'language':lang,'generalized':True},
                                   lambda o:check_project(normalize_empty_fields(o), topic, lang), s.max_repairs, local, progress)
            if errors:
                failed.append({'goal_id':goal.id,'reason':'project: ' + ' | '.join(errors)}); continue
            displays = {'questions':[]}
            if selected:
                displays, errors = _step(llm, 'link', base, prompts.links(qmeta), ProductionLinks,
                                         {'goal_id':goal.id,'questions':qmeta,'language':lang,'generalized':True},
                                         lambda o:check_links(o, selected, lang), s.max_repairs, local, progress)
                if errors:
                    failed.append({'goal_id':goal.id,'reason':'link: ' + ' | '.join(errors)}); continue
            # Keys always come from the source bank, never from a model's guess.
            for item in displays['questions']:
                q = bank.index[item['question_ref']]
                if q.kind == 'multiple_choice' and isinstance(q.answer_key, int) and 0 <= q.answer_key < len(item['choices']):
                    item['answer_text'] = item['choices'][q.answer_key]
                elif q.kind == 'true_false':
                    item['answer_text'] = (['True','False'] if lang == 'en' else ['صح','خطأ'])[1 if q.answer_key == 1 else 0]
            registration = REGISTRATION[lang]
            products.append({
                'id':f'kp_{goal.id}','goal_id':goal.id,'goal_text':goal.text,
                **{k:v for k,v in topic.items() if k not in ('goal_id','question_refs')},
                'sections':project['sections'],'questions':displays['questions'],
                'registration':{'title':topic['title'],'type':topic['product_type'],
                                'main_class':None,'sub_class':None,'language':registration['language'],
                                'edition':1,'year':s.edition_year,'parts':1,'origin':registration['origin'],
                                'page_count':None,'sensitive_topics':'none'},
                'review':{'status':'pending','warnings':[], 'reviewed_by':None,'reviewed_at':None}})
        except LLMError as e:
            failed.append({'goal_id':goal.id,'reason':str(e)})
        finally:
            for key,n in local.items():
                counters[key] = counters.get(key,0) + n
            if progress:
                failure = next((f['reason'] for f in failed if f['goal_id'] == goal.id), None)
                progress('goal_completed', goal_id=goal.id, completed_goals=number,
                         total_goals=len(goals), state='failed' if failure else 'completed',
                         **({'reason': failure} if failure else {}))
    regenerated = [p['goal_id'] for p in products]
    if only_goals and fresh:
        wanted = {g.id for g in goals}
        keep = [p for p in existing['products'] if p['goal_id'] not in wanted]
        failed = [f for f in existing.get('failed_goals',[]) if f['goal_id'] not in wanted] + failed
        order = {g.id:i for i,g in enumerate(bank.goals)}
        products = sorted(keep + products, key=lambda p:order[p['goal_id']])
    if only_goals:
        accounted = {p['goal_id'] for p in products} | {f['goal_id'] for f in failed}
        failed += [{'goal_id': g.id, 'reason': 'Not selected in this run; generate this goal to complete the lesson.'}
                   for g in bank.goals if g.id not in accounted]
    if not products:
        return {**res,'status':'failed','failed_goals':failed,'usage':llm.usage.as_dict(s)}
    record = {'schema_version':SCHEMA_VERSION,'kind':'knowledge_production',
              'document_uuid':doc.uuid or qrec.get('document_uuid'),
              'document_idx':str(doc.idx or qrec.get('document_idx')),
              'custom_id':doc.custom_id or qrec.get('custom_id') or None,
              'filename':doc.title,'subject':subject or None,'language':lang,
              'bank_fingerprint':bank.fingerprint,'content_fingerprint':doc.fingerprint,
              'prompt_version':PROMPT_VERSION,
              'generation':{'llm':llm.name,'unit':'one_product_per_worksheet_goal',
                            'content_source':'ai.summaries','goal_source':'ai.worksheets',
                            'question_policy':'optional_select_and_reuse',
                            'usage':{**llm.usage.as_dict(s),'repairs':counters},'requires_human_review':True},
              'products':products,'failed_goals':failed}
    if progress:
        progress('save' if store_record else 'validate', state='started', products=len(products))
    pending_path = None
    try:
        record = save_record(db,s.col_knowledge,record) if store_record else prepare_record(record)
    except PyMongoError as exc:
        pending_path = write_pending(record)
        if progress:
            progress('save', state='pending', pending_record=str(pending_path), reason=type(exc).__name__)
        return {**res, 'status':'pending_save', 'products':len(products),
                'regenerated':regenerated, 'failed_goals':failed, 'repairs':counters,
                'usage':llm.usage.as_dict(s), 'pending_record':str(pending_path),
                'reason':f'MongoDB write failed ({type(exc).__name__}); validated output queued at {pending_path}'}
    if progress:
        progress('save' if store_record else 'validate', state='completed', products=len(products))
    return {**res,'status':'partial' if failed else 'generated','products':len(products),
            'regenerated':regenerated,'failed_goals':failed,'repairs':counters,'usage':llm.usage.as_dict(s),
            **({'_record':record} if not store_record else {})}
