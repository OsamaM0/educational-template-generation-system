"""Database contract and command tests; no network or paid model calls."""
import json
from datetime import datetime

import mongomock
import pytest

import knowledge_production as cli
from kp.config import Settings
from kp.content import open_content
from kp.llm import LLMError, StubLLM, Usage
from kp.pipeline import generate_lesson
from kp.production_stub import block
from kp.store import RecordInvalid, check_record


@pytest.fixture
def settings():
    return Settings(mongo_uri="", llm_api_key="", mongo_db="ai", col_summaries="summaries", col_worksheets="worksheets",
                    col_questions="questions", col_knowledge="knowledge_productions")


@pytest.fixture
def db():
    database = mongomock.MongoClient().ai
    identity = {"document_uuid": "test-lesson-445", "document_idx": "445",
                "custom_id": "source-445", "filename": "Protecting accounts"}
    goals = ["Explain account security.", "Identify suspicious messages."]
    database.summaries.insert_one({**identity, "summary": {
        "opening": "Keeping accounts safe matters.",
        "summary": "Use a unique password and check suspicious messages before clicking links.",
        "ending": "Verify the sender through a separate trusted channel.",
    }})
    database.worksheets.insert_one({**identity, "worksheet": {
        "goals": goals, "_metadata": {"language": "english"},
    }})
    database.questions.insert_one({**identity, "questions": {
        "learning_goals": [{"id": f"goal_{i}", "text": goal, "cognitive_level": "understand"}
                           for i, goal in enumerate(goals, 1)],
        "multiple_choice": [{"id": "mc_1", "question": "Which password is safer?",
                             "choices": ["A unique password", "A shared password"],
                             "answer_key": 0, "goal_id": "goal_1"}],
    }})
    database.mindmaps.insert_one({**identity, "mindmap": {"nodeDataArray": []}})
    return database


def generate(db, settings, **kwargs):
    return generate_lesson("445", "idx", content_src=open_content(settings, db),
                           db=db, s=settings, llm=kwargs.pop("llm", StubLLM()), **kwargs)


def source_snapshot(db):
    return {name: list(db[name].find()) for name in ("summaries", "worksheets", "questions", "mindmaps")}


def test_usage_prices_each_model_and_cached_tokens(settings):
    from types import SimpleNamespace

    settings.model_creative = "creative/model"
    settings.model_link = "link/model"
    settings.price_model_math = settings.model_creative
    settings.price_model_normal = settings.model_link
    settings.price_math_in, settings.price_math_out = 2.0, 8.0
    settings.price_normal_in, settings.price_normal_out = 1.0, 3.0
    usage = Usage()
    usage.add("project", settings.model_creative, SimpleNamespace(
        prompt_tokens=1_000_000, completion_tokens=100_000,
        prompt_tokens_details=SimpleNamespace(cached_tokens=200_000)))
    other = Usage()
    other.add("link", settings.model_link, SimpleNamespace(
        prompt_tokens=500_000, completion_tokens=50_000,
        prompt_tokens_details=None))
    usage.merge(other)
    result = usage.as_dict(settings)
    assert result["total_tokens"] == 1_650_000
    assert result["by_model"][settings.model_creative]["cached_tokens"] == 200_000
    # No cached-token rate is configured, so cached input uses its model's input rate.
    assert result["cost_by_model_usd"] == {"creative/model": 2.8, "link/model": 0.65}
    assert result["estimated_cost_usd"] == 3.45


def test_save_original_contract_and_repeat_skips_model(db, settings):
    class Selecting(StubLLM):
        def complete(self, step, messages, schema, meta=None):
            result = super().complete(step, messages, schema, meta)
            if step == "topics":
                result["topics"][0]["question_refs"] = ["mc_1"]
            elif step == "project":
                for ref in meta["topic"]["question_refs"]:
                    result["sections"][0]["blocks"].append(block("question", question_ref=ref))
            elif step == "link":
                # The stored answer must still be derived from the source key.
                result["questions"][0]["answer_text"] = "An incorrect model guess"
            return result

    before = source_snapshot(db)
    result = generate(db, settings, llm=Selecting())
    assert result["status"] == "generated"
    record = db.knowledge_productions.find_one({"document_uuid": "test-lesson-445"})
    check_record(record)
    assert record["schema_version"] == "3.0.0"
    assert record["kind"] == "knowledge_production"
    assert record["document_idx"] == "445"
    assert record["custom_id"] == "source-445"
    assert isinstance(record["generated_at"], datetime)
    assert len(record["products"]) == 2
    assert all(p["review"]["status"] == "pending" for p in record["products"])
    question = record["products"][0]["questions"][0]
    assert question["question_ref"] == "mc_1"
    assert question["answer_text"] == question["choices"][0]

    class NeverCall(StubLLM):
        def complete(self, *args, **kwargs):
            pytest.fail("An unchanged lesson should not call the model")

    assert generate(db, settings, llm=NeverCall())["status"] == "up_to_date"
    assert db.knowledge_productions.count_documents({}) == 1
    assert source_snapshot(db) == before


@pytest.mark.parametrize("collection,update", [
    ("summaries", {"summary.ending": "Use multiple layers of account protection."}),
    ("worksheets", {"worksheet.goals.0": "Explain strong and unique passwords."}),
    ("questions", {"questions.multiple_choice.0.question": "Choose the safer password policy."}),
])
def test_changed_input_regenerates_one_existing_record(db, settings, collection, update):
    generate(db, settings)
    db[collection].update_one({}, {"$set": update})
    assert generate(db, settings)["status"] == "generated"
    assert db.knowledge_productions.count_documents({}) == 1


def test_no_question_bank_still_creates_products(db, settings):
    db.questions.delete_many({})
    result = generate(db, settings)
    assert result["status"] == "generated"
    record = db.knowledge_productions.find_one()
    assert len(record["products"]) == 2
    assert all(product["questions"] == [] for product in record["products"])


@pytest.mark.parametrize("collection,status", [("summaries", "no_content"), ("worksheets", "no_goals")])
def test_missing_prerequisites_do_not_write(db, settings, collection, status):
    db[collection].delete_many({})
    assert generate(db, settings)["status"] == status
    assert db.knowledge_productions.count_documents({}) == 0


def test_goal_subset_keeps_other_products_and_rejects_stale_record(db, settings):
    generate(db, settings)
    before = db.knowledge_productions.find_one()
    result = generate(db, settings, only_goals={"goal_1"})
    after = db.knowledge_productions.find_one()
    assert result["regenerated"] == ["goal_1"]
    assert after["products"][1] == before["products"][1]
    db.summaries.update_one({}, {"$set": {"summary.ending": "Changed grounding content."}})
    result = generate(db, settings, only_goals={"goal_1"})
    assert result["status"] == "failed"
    assert db.knowledge_productions.find_one() == after


def test_invalid_resource_is_rejected_before_save(db, settings):
    record = generate(db, settings, store_record=False)["_record"]
    record["products"][0]["sections"][0]["blocks"] = [
        block("table", columns=["One", "Two"], rows=[{"cells": ["Only one cell"]}])]
    with pytest.raises(RecordInvalid):
        check_record(record)
    assert db.knowledge_productions.count_documents({}) == 0


def test_partial_failure_reports_failed_goal(db, settings):
    class Fault(StubLLM):
        def complete(self, step, messages, schema, meta=None):
            if step == "project" and meta["goal_id"] == "goal_2":
                raise LLMError("test provider failure")
            return super().complete(step, messages, schema, meta)

    result = generate(db, settings, llm=Fault())
    assert result["status"] == "partial"
    assert result["products"] == 1
    assert result["failed_goals"][0]["goal_id"] == "goal_2"
    preserved = db.knowledge_productions.find_one()['products'][0]
    class Counting(StubLLM):
        def __init__(self):
            super().__init__()
            self.projects = []
        def complete(self, step, messages, schema, meta=None):
            if step == 'project':
                self.projects.append(meta['goal_id'])
            return super().complete(step, messages, schema, meta)

    model = Counting()
    assert generate(db, settings, llm=model)["status"] == "generated"
    assert model.projects == ['goal_2']
    assert db.knowledge_productions.find_one()['products'][0] == preserved


def test_cli_dry_run_never_initializes_model_or_collection(db, settings, tmp_path, monkeypatch):
    before = source_snapshot(db)
    def forbidden(*args, **kwargs):
        pytest.fail("Dry run must not call a paid model or maintain a collection")
    monkeypatch.setattr(cli, "OpenRouterLLM", forbidden)
    monkeypatch.setattr(cli, "ensure_collection", forbidden)
    report = tmp_path / "dry-run.json"
    args = cli.parse_args(["--all", "--dry-run", "--report", str(report)])
    assert cli.run(args, db, settings) == 0
    payload = json.loads(report.read_text())
    assert payload["counts"] == {"dry_run": 1}
    assert payload["usage"]["calls"] == 0
    assert payload["results"][0]["plan"]["calls"] == 4
    journal_rows = [json.loads(line) for line in report.with_suffix(".jsonl").read_text().splitlines()]
    assert len(journal_rows) == 1
    assert journal_rows[0]["result"]["status"] == "dry_run"
    assert journal_rows[0]["usage"]["total_tokens"] == 0
    assert "knowledge_productions" not in db.list_collection_names()
    assert source_snapshot(db) == before


def test_cli_local_output_is_schema_valid_and_db_untouched(db, settings, tmp_path):
    before = source_snapshot(db)
    args = cli.parse_args(["--lesson-source-id", "445", "--llm", "stub",
                           "--local-out", str(tmp_path / "records"),
                           "--report", str(tmp_path / "report.json")])
    assert cli.run(args, db, settings) == 0
    files = list((tmp_path / "records").glob("*.json"))
    assert len(files) == 1
    check_record(json.loads(files[0].read_text()))
    assert "knowledge_productions" not in db.list_collection_names()
    assert source_snapshot(db) == before


def test_cli_generates_only_destination_and_deduplicates_ids(db, settings, tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "OpenRouterLLM", lambda settings: StubLLM())
    before = source_snapshot(db)
    args = cli.parse_args(["--lesson-id", "445", "445", "--workers", "2",
                           "--report", str(tmp_path / "report.json")])
    assert cli.run(args, db, settings) == 0
    assert db.knowledge_productions.count_documents({}) == 1
    assert json.loads(args.report.read_text())["counts"] == {"generated": 1}
    assert source_snapshot(db) == before


def test_cli_partial_run_has_nonzero_exit(db, settings, tmp_path, monkeypatch):
    class Fault(StubLLM):
        def complete(self, step, messages, schema, meta=None):
            if step == "project" and meta["goal_id"] == "goal_2":
                raise LLMError("test provider failure")
            return super().complete(step, messages, schema, meta)
    monkeypatch.setattr(cli, "OpenRouterLLM", lambda settings: Fault())
    args = cli.parse_args(["--all", "--report", str(tmp_path / "report.json")])
    assert cli.run(args, db, settings) == 1
    assert json.loads(args.report.read_text())["counts"] == {"partial": 1}


@pytest.mark.parametrize("flags", [
    ["--llm", "stub"], ["--llm", "replay"], ["--workers", "0"],
    ["--limit", "0"], ["--dry-run", "--setup-collection"], ["--goals", ","],
])
def test_cli_rejects_invalid_options(flags):
    with pytest.raises(SystemExit) as error:
        cli.parse_args(["--all", *flags])
    assert error.value.code == 2


def test_settings_use_shared_models_and_allow_specific_overrides(monkeypatch):
    monkeypatch.setenv("LLM_MODEL_MATH", "shared/creative")
    monkeypatch.setenv("LLM_MODEL_NORMAL", "shared/link")
    monkeypatch.delenv("KP_MODEL_CREATIVE", raising=False)
    monkeypatch.delenv("KP_MODEL_LINK", raising=False)
    assert Settings().model_creative == "shared/creative"
    assert Settings().model_link == "shared/link"
    monkeypatch.setenv("KP_MODEL_CREATIVE", "specific/creative")
    monkeypatch.setenv("KP_MODEL_LINK", "specific/link")
    assert Settings().model_creative == "specific/creative"
    assert Settings().model_link == "specific/link"


def test_first_selected_goal_run_does_not_mark_whole_lesson_complete(db, settings):
    result = generate(db, settings, only_goals={'goal_1'})
    assert result['status'] == 'partial'
    assert [f['goal_id'] for f in result['failed_goals']] == ['goal_2']
    assert generate(db, settings)['status'] == 'generated'
    assert len(db.knowledge_productions.find_one()['products']) == 2
    assert generate(db, settings)['status'] == 'up_to_date'


def test_each_goal_reports_completion_and_keeps_lesson_title(db, settings):
    from utils.run_progress import PREFIX, read_progress
    events = []
    def progress(stage, **fields):
        events.append({'event': 'stage', 'lesson_id': '445', 'stage': stage, **fields})
    assert generate(db, settings, progress=progress)['status'] == 'generated'
    completions = [e for e in events if e['stage'] == 'goal_completed']
    assert [e['completed_goals'] for e in completions] == [1, 2]
    state = read_progress([PREFIX + json.dumps(e) for e in events])
    active = state['active']['445']
    assert active['title'] == 'Protecting accounts'
    assert active['completed_goals'] == active['total_goals'] == 2
