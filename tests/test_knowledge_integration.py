"""End-to-end offline checks for batch, lesson selection and frontend runs."""
import json
from pathlib import Path

import mongomock
import pytest

from clients.mongo_client import MongoDBClient, AI_TEMPLATE_COLLECTIONS
from kp.config import Settings
from kp.integration import generate_for_document
from kp.llm import StubLLM
from processors.batch_processor import BatchProcessor
from questions_cycle import build_lesson_documents
import results_dashboard as dashboard
from utils.run_progress import PREFIX, read_progress


@pytest.fixture
def mongo():
    client = MongoDBClient('mongodb://unused')
    mock = mongomock.MongoClient()
    client.storage_db = mock.ai
    client.lessons_db = mock['ien-v2']
    client.goals_db = mock.ien
    return client


DOCUMENT = {'uuid': 'lesson-445', 'idx': '445', 'filename': 'Account security',
            'content': 'Use unique passwords. Verify suspicious messages before clicking links.'}
GOALS = ['Explain account security.', 'Identify suspicious messages.']


class Generator:
    def __init__(self):
        self.calls = []
        self.content_processor = self

    def generate_learning_goals(self, content, count):
        self.calls.append('goals')
        return GOALS

    def generate_summary(self, **kwargs):
        self.calls.append('summary')
        return {'opening': 'Keeping accounts safe.', 'summary': DOCUMENT['content'], 'ending': 'Verify the sender.'}

    def generate_worksheet(self, **kwargs):
        self.calls.append('worksheet')
        return {'goals': GOALS}

    def generate_goal_based_questions(self, **kwargs):
        self.calls.append('questions')
        return {'learning_goals': [{'id': f'goal_{i}', 'text': g} for i, g in enumerate(GOALS, 1)]}

    def generate_mindmap(self, **kwargs):
        self.calls.append('mindmap')
        return {'nodeDataArray': [{'key': 0, 'text': 'Account security'}]}


@pytest.fixture
def stub_integration(monkeypatch):
    # Real loader, validation and persistence, replacing only the paid model.
    from kp import integration
    monkeypatch.setattr(integration, 'OpenRouterLLM', lambda settings: StubLLM())


def seed_sources(mongo):
    mongo.store_summary(DOCUMENT, Generator().generate_summary())
    mongo.store_worksheet(DOCUMENT, GOALS, {'goals': GOALS})


def test_full_batch_saves_all_five_and_reports_progress(mongo, stub_integration, capsys):
    gen = Generator()
    processor = BatchProcessor(None, mongo, gen)
    stats = processor.process_documents([DOCUMENT], list(AI_TEMPLATE_COLLECTIONS))
    assert gen.calls == ['summary', 'goals', 'worksheet', 'questions', 'mindmap']
    assert all(mongo.storage_db[name].count_documents({'document_uuid': DOCUMENT['uuid']}) == 1
               for name in AI_TEMPLATE_COLLECTIONS)
    record = mongo.storage_db.knowledge_productions.find_one()
    assert [p['goal_text'] for p in record['products']] == GOALS
    assert all(p['review']['status'] == 'pending' for p in record['products'])
    assert stats.successful_knowledge_productions == 1
    progress = read_progress(capsys.readouterr().out.splitlines())
    assert progress['total'] == progress['completed'] == progress['successful'] == 1
    assert progress['finished'] and not progress['active']


def test_knowledge_only_batch_no_extra_generation_and_stale_rerun(mongo, stub_integration):
    seed_sources(mongo)
    gen = Generator()
    processor = BatchProcessor(None, mongo, gen)
    doc = {**DOCUMENT, 'content': ''}
    assert processor._process_single_document(doc, ['knowledge_productions'], True) == 'generated'
    record = mongo.storage_db.knowledge_productions.find_one()
    assert processor._process_single_document(doc, ['knowledge_productions'], True) == 'up_to_date'
    assert mongo.storage_db.knowledge_productions.find_one() == record
    mongo.storage_db.worksheets.update_one({}, {'$set': {'worksheet.goals': GOALS[:1]}})
    assert processor._process_single_document(doc, ['knowledge_productions'], True) == 'generated'
    assert len(mongo.storage_db.knowledge_productions.find_one()['products']) == 1
    assert not gen.calls


def test_bulk_knowledge_adds_missing_prerequisites(mongo, stub_integration):
    gen = Generator()
    assert BatchProcessor(None, mongo, gen)._process_single_document(
        DOCUMENT, ['knowledge_productions'], True) == 'generated'
    assert gen.calls == ['summary', 'goals', 'worksheet']
    assert mongo.storage_db.knowledge_productions.count_documents({}) == 1


def test_missing_goals_failure_reaches_stats_and_progress(mongo, stub_integration, capsys):
    mongo.store_summary(DOCUMENT, Generator().generate_summary())
    doc = {**DOCUMENT, 'template_types': ['knowledge_productions']}
    stats = BatchProcessor(None, mongo, Generator()).process_documents([doc], ['knowledge_productions'])
    assert stats.failed_knowledge_productions == 1
    assert mongo.storage_db.knowledge_productions.count_documents({}) == 0
    assert read_progress(capsys.readouterr().out.splitlines())['failed'] == 1


def test_complete_question_lessons_can_receive_other_templates(mongo, monkeypatch):
    seed_sources(mongo)
    mongo.store_questions(DOCUMENT, GOALS, {'multiple_choice': []})
    mongo.lessons_db.lessons.insert_one({'lessonId': 445, 'title': DOCUMENT['filename']})
    class Tahdiri:
        def get_questions_for_api_lesson(self, lesson_id):
            raise AssertionError('Existing summaries should be reused')
    def full_scan():
        raise AssertionError('Explicit lesson IDs must use bounded lookups')
    monkeypatch.setattr(mongo, 'get_template_uuid_sets', full_scan)
    monkeypatch.setattr(mongo, 'get_all_lesson_file_info', full_scan)
    docs = build_lesson_documents(mongo, Tahdiri(), lesson_source_ids=[445],
                                 template_types=['mindmaps', 'knowledge_productions'])
    assert len(docs) == 1
    assert docs[0]['template_types'] == ['mindmaps', 'knowledge_productions']
    assert docs[0]['content_source'] == 'ai-summary'


def test_limited_cycle_prioritizes_missing_knowledge(mongo, stub_integration):
    seed_sources(mongo)
    generate_for_document(DOCUMENT, mongo.storage_db)
    second = {**DOCUMENT, 'uuid':'lesson-446', 'idx':'446', 'filename':'Safe messages'}
    mongo.store_summary(second, Generator().generate_summary())
    mongo.store_worksheet(second, GOALS, {'goals': GOALS})
    mongo.lessons_db.lessons.insert_many([{'lessonId':445,'title':DOCUMENT['filename']},
                                         {'lessonId':446,'title':second['filename']}])
    class Tahdiri:
        def get_questions_for_api_lesson(self, lesson_id):
            raise AssertionError('Existing summaries should be reused')
    docs = build_lesson_documents(mongo, Tahdiri(), limit=1,
                                  template_types=['knowledge_productions'])
    assert [doc['uuid'] for doc in docs] == [second['uuid']]


def test_frontend_routes_backfill_and_mixed_cycle():
    cmd = dashboard.build_run_command({'templates': ['knowledge_productions'], 'lesson_ids': '445, 446',
                                       'force': True, 'dry_run': True, 'workers': 3})
    assert 'knowledge_production.py' in cmd
    assert cmd[cmd.index('--lesson-id') + 1:cmd.index('--force')] == ['445', '446']
    assert '--dry-run' in cmd
    mixed = dashboard.build_run_command({'templates': ['summaries', 'knowledge_productions'], 'force': True})
    assert 'questions_cycle.py' in mixed and '--force-knowledge' in mixed
    assert '--all' in dashboard.build_run_command({'templates': ['knowledge_productions']})
    assert '--resume-pending' in dashboard.build_run_command({'resume_pending': True})
    with pytest.raises(ValueError, match='lesson ids'):
        dashboard.build_run_command({'templates': ['knowledge_productions'], 'lesson_ids': 'wrong-id'})


def test_frontend_lists_and_fetches_productions(mongo, stub_integration, monkeypatch):
    seed_sources(mongo)
    generate_for_document(DOCUMENT, mongo.storage_db)
    monkeypatch.setattr(dashboard, 'get_mongo', lambda: mongo)
    monkeypatch.setattr(dashboard, '_index_cache', {'at': 0, 'lessons': []})
    assert 'knowledge_productions' in dashboard.lesson_index()[0]['templates']
    assert dashboard.lesson_page(status='complete')['total'] == 1
    assert dashboard.lesson_page(status='missing')['total'] == 0
    assert dashboard.lesson_stats()['counts']['knowledge_productions'] == 1
    assert len(dashboard.lesson_detail(DOCUMENT['uuid'])['knowledge_productions']['products']) == 2


def test_frontend_shows_detached_backfill_and_blocks_duplicate_run(tmp_path, monkeypatch):
    log = tmp_path / 'kp-backfill-test.log'
    log.write_text(PREFIX + json.dumps({'event': 'run_started', 'total': 10}) + '\n' +
                   PREFIX + json.dumps({'event': 'stage', 'lesson_id': '445',
                                        'stage': 'project', 'goal_id': 'goal_2'}) + '\n')
    log.with_suffix('.jsonl').write_text(json.dumps({
        'result': {'lesson_id': '444', 'status': 'generated', 'products': 2},
        'usage': {'calls': 3, 'input_tokens': 500, 'cached_tokens': 0,
                  'output_tokens': 200, 'total_tokens': 700, 'estimated_cost_usd': 0.002},
    }) + '\n')
    monkeypatch.setattr(dashboard, 'LOG_DIR', tmp_path)
    monkeypatch.setattr(dashboard, '_backfill_running', lambda: True)
    monkeypatch.setattr(dashboard, '_backfill_cache', {'key': None, 'at': 0, 'value': None})
    status = dashboard.backfill_status()
    assert status['running'] and status['total'] == 10 and status['completed'] == 1
    assert status['usage']['total_tokens'] == 700
    assert status['active'][0]['goal_id'] == 'goal_2'
    assert dashboard.backfill_status()['completed'] == 1
    with pytest.raises(RuntimeError, match='all-lesson knowledge run is active'):
        dashboard.start_run({'templates': ['knowledge_productions']})


def test_frontend_status_reports_failed_subprocess(tmp_path, monkeypatch):
    class Failed:
        def poll(self):
            return 1
    log = tmp_path / 'run.log'
    log.write_text(PREFIX + json.dumps({'event':'run_started', 'total':1}) + '\n' +
                   PREFIX + json.dumps({'event':'lesson_completed', 'lesson_id':'445', 'status':'partial'}) + '\n')
    monkeypatch.setattr(dashboard, 'RUN_LOG', log)
    monkeypatch.setattr(dashboard, 'run_proc', {'proc': Failed(), 'cmd': [], 'log': None})
    status = dashboard.run_status()
    assert not status['running'] and status['exit_code'] == 1
    assert status['progress']['failed'] == 1


def test_discovery_is_visible_until_lesson_selection_finishes():
    started = PREFIX + json.dumps({'event':'discovery_started', 'lesson_id':'selection',
                                   'stage':'select_lessons'})
    completed = PREFIX + json.dumps({'event':'discovery_completed', 'lesson_id':'selection'})
    assert 'selection' in read_progress([started])['active']
    assert not read_progress([started, completed])['active']


@pytest.mark.parametrize('ceiling,always_truncated,expected_calls', [
    (12000, False, 2), (12000, True, 2), (6000, True, 1),
])
def test_truncated_provider_response_has_bounded_token_retry(ceiling, always_truncated, expected_calls):
    from types import SimpleNamespace as NS
    from openai import LengthFinishReasonError
    from kp.llm import OpenRouterLLM, LLMError
    from kp.production_models import ProductionTopics
    usage = NS(prompt_tokens=10, completion_tokens=20, prompt_tokens_details=None)
    calls = []
    def parse(**kwargs):
        calls.append(kwargs)
        if always_truncated or len(calls) == 1:
            raise LengthFinishReasonError(completion=NS(usage=usage))
        return NS(choices=[NS(message=NS(refusal=None, parsed=ProductionTopics(topics=[])))], usage=usage)
    client = NS(base_url='https://openrouter.ai/api/v1', chat=NS(completions=NS(parse=parse)))
    settings = Settings(llm_api_key='', max_tokens=6000, max_retry_tokens=ceiling)
    model = OpenRouterLLM(settings, client=client)
    events = []
    meta = {'_progress': lambda stage, **fields: events.append(fields)}
    if always_truncated:
        with pytest.raises(LLMError, match='token limit'):
            model.complete('topics', [], ProductionTopics, meta)
    else:
        assert model.complete('topics', [], ProductionTopics, meta) == {'topics': []}
    assert len(calls) == model.usage.calls == expected_calls
    assert calls[0]['max_tokens'] == 6000
    if expected_calls == 2:
        assert calls[1]['max_tokens'] == 12000
        assert events[0]['reason'] == 'token_limit'
        if not always_truncated:
            assert model._kwargs_for(settings.model_creative, 'project')['max_tokens'] == 12000
    else:
        assert not events


def test_batch_rejects_destination_collision_without_writing_sources(mongo):
    seed_sources(mongo)
    before = list(mongo.storage_db.summaries.find())
    with pytest.raises(ValueError, match='destination'):
        generate_for_document(DOCUMENT, mongo.storage_db, settings=Settings(col_knowledge='summaries'), llm=StubLLM())
    assert list(mongo.storage_db.summaries.find()) == before


def test_mechanical_links_use_configured_reasoning_budget():
    from types import SimpleNamespace as NS
    from kp.llm import OpenRouterLLM
    settings = Settings(llm_api_key='', link_reasoning_effort='low')
    model = OpenRouterLLM(settings, client=NS(base_url='https://openrouter.ai/api/v1'))
    assert model._kwargs_for(settings.model_creative, 'topics')['extra_body'] == {'reasoning': {'effort': 'low'}}
    assert model._kwargs_for(settings.model_link, 'link')['extra_body'] == {'reasoning': {'effort': 'low'}}
    settings.link_reasoning_effort = 'provider'
    assert 'extra_body' not in model._kwargs_for(settings.model_link, 'link')
    settings.creative_reasoning_effort = 'low'
    assert model._kwargs_for(settings.model_creative, 'project')['extra_body'] == {'reasoning': {'effort': 'low'}}
    settings.creative_reasoning_effort = 'provider'
    assert 'extra_body' not in model._kwargs_for(settings.model_creative, 'project')


def test_repair_diagnostics_identify_invalid_block_and_missing_question():
    from kp.production_stub import block
    from kp.production_validate import check_project
    errors = check_project({'sections':[{'id':'cards', 'title':'Examples',
                                        'blocks':[block('cards', items=[''])]}]},
                           {'question_refs':['mc_1']}, 'en')
    assert any('cards/blocks[0]' in error and 'nonblank strings' in error for error in errors)
    assert any("Missing refs: ['mc_1']" in error for error in errors)


def test_empty_unused_fields_are_canonicalized_without_discarding_content():
    from kp.production_stub import block
    from kp.production_validate import normalize_empty_fields, check_project
    paragraph = block('paragraph', text='A substantive explanation.', items=[], columns=[], rows=[], question_ref='')
    out = {'sections':[{'id':'example', 'title':'Example', 'blocks':[paragraph]}]}
    normalize_empty_fields(out)
    assert check_project(out, {'question_refs':[]}, 'en') == []
    assert paragraph['text'] == 'A substantive explanation.'
    paragraph['items'] = ['Further useful content.']
    normalize_empty_fields(out)
    assert paragraph['items'] == ['Further useful content.']
    assert any('unused items must be null' in e for e in check_project(out, {'question_refs':[]}, 'en'))


@pytest.mark.parametrize('fenced,valid', [('```json\n{"questions": []}\n```', True),
                                         ('not JSON', False)])
def test_provider_fenced_json_is_recovered_or_reported_as_goal_failure(fenced, valid):
    from types import SimpleNamespace as NS
    from pydantic import TypeAdapter, ValidationError
    from kp.llm import OpenRouterLLM, LLMError
    from kp.production_models import ProductionLinks
    def parse(**kwargs):
        TypeAdapter(ProductionLinks).validate_json(fenced)
    model = OpenRouterLLM(Settings(llm_api_key=''),
                          client=NS(base_url='https://openrouter.ai/api/v1',
                                    chat=NS(completions=NS(parse=parse))))
    if valid:
        assert model.complete('link', [], ProductionLinks) == {'questions': []}
        assert model.usage.calls == 1
    else:
        with pytest.raises(LLMError, match='invalid structured JSON'):
            model.complete('link', [], ProductionLinks)


def test_invalid_provider_json_retries_once_with_structured_output():
    from types import SimpleNamespace as NS
    from pydantic import TypeAdapter
    from kp.llm import OpenRouterLLM
    from kp.production_models import ProductionLinks
    calls = []
    def parse(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            TypeAdapter(ProductionLinks).validate_json('not JSON')
        return NS(choices=[NS(message=NS(refusal=None, parsed=ProductionLinks(questions=[])))], usage=None)
    model = OpenRouterLLM(Settings(llm_api_key=''),
                          client=NS(base_url='https://openrouter.ai/api/v1',
                                    chat=NS(completions=NS(parse=parse))))
    events = []
    assert model.complete('link', [], ProductionLinks,
                          {'_progress':lambda stage, **fields: events.append(fields)}) == {'questions': []}
    assert len(calls) == 2 and events[0]['reason'] == 'invalid_json'


def test_database_write_outage_queues_validated_record_for_later_import(mongo, stub_integration,
                                                                        monkeypatch, tmp_path):
    from pymongo.errors import ServerSelectionTimeoutError
    import knowledge_production as cli
    from kp import production
    seed_sources(mongo)
    monkeypatch.setenv('KP_PENDING_DIR', str(tmp_path / 'pending'))
    with monkeypatch.context() as patched:
        def unavailable(*args, **kwargs):
            raise ServerSelectionTimeoutError('database unavailable')
        patched.setattr(production, 'save_record', unavailable)
        result = generate_for_document(DOCUMENT, mongo.storage_db)
    assert result['status'] == 'pending_save'
    path = Path(result['pending_record'])
    assert path.is_file() and mongo.storage_db.knowledge_productions.count_documents({}) == 0
    settings = Settings(mongo_uri='', llm_api_key='')
    args = cli.parse_args(['--resume-pending', str(path), '--report', str(tmp_path / 'restore.json')])
    assert cli.run(args, mongo.storage_db, settings) == 0
    assert not path.exists()
    assert len(mongo.storage_db.knowledge_productions.find_one()['products']) == 2
    assert json.loads((tmp_path / 'restore.json').read_text())['counts'] == {'restored': 1}


def test_pending_import_refuses_changed_sources(mongo, stub_integration, monkeypatch, tmp_path):
    from pymongo.errors import ServerSelectionTimeoutError
    from kp import production
    from kp.pending import restore_pending
    seed_sources(mongo)
    monkeypatch.setenv('KP_PENDING_DIR', str(tmp_path / 'pending'))
    with monkeypatch.context() as patched:
        patched.setattr(production, 'save_record', lambda *args: (_ for _ in ()).throw(
            ServerSelectionTimeoutError('database unavailable')))
        result = generate_for_document(DOCUMENT, mongo.storage_db)
    path = Path(result['pending_record'])
    mongo.storage_db.worksheets.update_one({}, {'$set':{'worksheet.goals':GOALS[:1]}})
    with pytest.raises(ValueError, match='stale'):
        restore_pending(path, mongo.storage_db, Settings(mongo_uri='', llm_api_key=''))
    assert path.exists() and mongo.storage_db.knowledge_productions.count_documents({}) == 0
