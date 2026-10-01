"""Structural and source checks, without prescribing an educational format."""
from collections import Counter
from .validate import lang_errors

BLOCK_FIELDS = {'paragraph': {'text'}, 'callout': {'text'}, 'response_space': {'text'},
                'bullets': {'items'}, 'steps': {'items'}, 'cards': {'items'},
                'table': {'columns', 'rows'}, 'question': {'question_ref'}}


def normalize_empty_fields(out):
    """Canonicalize empty unused fields; preserve every substantive value for validation."""
    for section in out['sections']:
        for block in section['blocks']:
            used = BLOCK_FIELDS[block['kind']]
            for key in ('text', 'items', 'columns', 'rows', 'question_ref'):
                if key not in used and block[key] in ('', []):
                    block[key] = None
    return out


def check_topics(out, goals, candidates, limit, lang):
    topics = out['topics']
    errors = []
    expected = Counter(g.id for g in goals)
    if Counter(t['goal_id'] for t in topics) != expected:
        errors.append('Return exactly one topic for each supplied goal, without extra goals.')
    titles = [t['title'].strip() for t in topics]
    if len(titles) != len(set(titles)):
        errors.append('Give each product a distinct, goal-specific title.')
    for t in topics:
        for key in ('product_type', 'title', 'purpose', 'audience', 'lesson_connection'):
            if not t[key].strip():
                errors.append(f"{t['goal_id']}: {key} must explain the actual resource.")
        refs = t['question_refs']
        allowed = {q.id for q in candidates.get(t['goal_id'], [])}
        if len(refs) != len(set(refs)) or not set(refs) <= allowed or len(refs) > limit:
            errors.append(f"{t['goal_id']}: choose unique optional question refs from this goal, at most {limit}.")
    return errors + (lang_errors(topics) if lang == 'en' else [])


def check_project(out, topic, lang):
    errors, refs = [], []
    sections = out['sections']
    if not sections or len(sections) > 12:
        errors.append('Use 1–12 useful sections; do not create an empty resource.')
    ids = [s['id'] for s in sections]
    if any(not x.strip() for x in ids) or len(ids) != len(set(ids)):
        errors.append('Section IDs must be non-empty and unique.')
    knowledge = 0
    for section in sections:
        if not section['title'].strip() or not section['blocks']:
            errors.append(f"Section {section['id']} needs a title and content.")
        for index, b in enumerate(section['blocks']):
            kind = b['kind']
            location = f"{section['id']}/blocks[{index}]"
            valid = False
            fields = BLOCK_FIELDS[kind]
            for key in ('text','items','columns','rows','question_ref'):
                if key not in fields and b[key] is not None:
                    errors.append(f'{location}: {kind} unused {key} must be null.')
            if kind in ('paragraph', 'callout', 'response_space'):
                valid = bool((b['text'] or '').strip())
            elif kind in ('bullets', 'steps', 'cards'):
                valid = bool(b['items']) and all(x.strip() for x in b['items'])
            elif kind == 'table':
                valid = bool(b['columns']) and bool(b['rows']) and all(
                    len(r['cells']) == len(b['columns']) for r in b['rows']) and any(
                    cell.strip() for r in (b['rows'] or []) for cell in r['cells'])
                if b['columns'] and len(b['columns']) > 5:
                    errors.append(f'{location}: use at most five table columns so the resource is legible.')
            elif kind == 'question':
                valid = bool(b['question_ref'])
                refs.append(b['question_ref'])
                if b['teacher_only']:
                    errors.append(f'{location}: question blocks must be visible to learners; answers are hidden separately.')
            if not valid:
                requirements = {
                    'paragraph': 'nonblank text', 'callout': 'nonblank text',
                    'response_space': 'nonblank prompt text',
                    'bullets': 'items containing nonblank strings', 'steps': 'items containing nonblank strings',
                    'cards': 'items containing nonblank strings; use response_space for blank learner responses',
                    'table': 'nonempty columns and rows with the same cell count as columns',
                    'question': 'a selected question_ref',
                }
                errors.append(f"{location}: {kind} requires {requirements[kind]}.")
            if valid and not b['teacher_only'] and kind not in ('question', 'response_space'):
                knowledge += 1
    if Counter(refs) != Counter(topic['question_refs']):
        missing = list((Counter(topic['question_refs']) - Counter(refs)).elements())
        extra = list((Counter(refs) - Counter(topic['question_refs'])).elements())
        errors.append(f'Use each selected question exactly once. Missing refs: {missing}; extra refs: {extra}.')
    if not knowledge:
        errors.append('Write useful knowledge content visible to learners, beyond questions and blank response areas.')
    return errors + (lang_errors(out) if lang == 'en' else [])


def check_links(out, selected, lang):
    errors = []
    items = out['questions']
    if Counter(x['question_ref'] for x in items) != Counter(q.id for q in selected):
        errors.append('Return exactly one faithful display for each selected question.')
    by_id = {q.id:q for q in selected}
    for item in items:
        q = by_id.get(item['question_ref'])
        if not q:
            continue
        if not item['question_text'].strip() or not item['answer_text'].strip():
            errors.append(f'{q.id}: question and answer must be non-empty.')
        if q.kind == 'multiple_choice':
            if not item['choices'] or len(item['choices']) != len(q.choices):
                errors.append(f'{q.id}: preserve choice count and order.')
        elif item['choices'] is not None:
            errors.append(f'{q.id}: only multiple-choice questions need choices.')
    return errors + (lang_errors(out) if lang == 'en' else [])
