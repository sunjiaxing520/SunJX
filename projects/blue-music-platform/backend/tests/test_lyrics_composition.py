from copy import deepcopy
from datetime import date
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, select, text

from app.adapters.text_generation import LocalTextProvider, ProviderResult
from app.core.database import get_db
from app.models import AnalysisReport, LyricsTask
from tests.test_workflows import (
    WorkflowContext, _collect_sample, _headers, workflow_context,
)


def _post(context: WorkflowContext, payload: dict):
    return context.client.post(
        "/api/v1/lyrics/compose", headers=_headers(context), json=payload,
    )


def _essences(context: WorkflowContext):
    return context.client.get(
        "/api/v1/lyrics-memory/events", headers=_headers(context),
        params={"event_type": "prompt_essence"},
    ).json()


@pytest.mark.parametrize("payload", [
    {"mode": "prompt"},
    {"mode": "prompt", "prompt": "  "},
    {"mode": "prompt", "prompt": "写一首励志歌曲", "analysis_report_id": 1},
    {"mode": "prompt", "prompt": "写一首励志歌曲", "theme": "绕过新入口"},
    {"mode": "analysis"},
    {"mode": "analysis", "analysis_report_id": 1},
    {"mode": "analysis", "analysis_report_id": 1, "direction_index": -1},
    {"mode": "prompt", "prompt": "歌" * 2001},
    {"mode": "prompt", "prompt": "今天天气怎么样"},
])
def test_composition_rejects_invalid_input_before_task_creation(workflow_context, payload):
    response = _post(workflow_context, payload)
    assert response.status_code == 422
    history = workflow_context.client.get(
        "/api/v1/lyrics/tasks", headers=_headers(workflow_context),
    ).json()
    assert history["total"] == 0
    assert _essences(workflow_context)["total"] == 0


def test_prompt_composition_persists_features_and_original_input(workflow_context, monkeypatch):
    original = LocalTextProvider.generate_lyrics
    seen = []

    def generate(self, context, variation):
        if not context.get("composition"):
            return original(self, context, variation)
        seen.append(deepcopy(context))
        result = original(self, context, variation)
        result.output.creation_features.theme = "兄弟重逢"
        result.output.creation_features.genre_tags = ["民谣"]
        result.output.creation_features.tempo = "slow"
        return result

    monkeypatch.setattr(LocalTextProvider, "generate_lyrics", generate)
    prompt = "写一首兄弟重逢的歌，歌名《并肩》，副歌温暖有力量。" + "用城市夜晚的画面叙事。" * 60
    response = _post(workflow_context, {"mode": "prompt", "prompt": prompt})
    assert response.status_code == 201, response.text
    task = response.json()
    assert task["theme"] == "兄弟重逢"
    assert task["genre_tags"] == ["民谣"]
    assert task["analysis_report_id"] is None
    assert task["versions"][0]["title"] == "并肩"
    assert len(task["api_usage"]) == 1
    sections = task["versions"][0]["sections"]
    assert [item["name"] for item in sections] == [
        "Verse 1", "Verse 2", "Chorus1", "Chorus2", "Interlude",
        "Verse 2", "Chorus1", "Chorus2", "Chorus1", "Chorus2", "Outro",
    ]
    assert sections[4]["content"] == sections[10]["content"] == ""
    assert sections[2]["content"] == sections[6]["content"] == sections[8]["content"]
    assert sections[3]["content"] == sections[7]["content"] == sections[9]["content"]
    assert sections[2]["content"].splitlines()[0] == sections[3]["content"].splitlines()[0]
    assert _essences(workflow_context)["total"] == 1
    assert seen[0]["lyrics_skill_memory"]

    regenerated = workflow_context.client.post(
        f"/api/v1/lyrics/tasks/{task['id']}/regenerate", headers=_headers(workflow_context),
    )
    assert regenerated.status_code == 200, regenerated.text
    assert len(regenerated.json()["versions"]) == 2
    assert len(seen) == 2
    assert seen[1]["composition"] == seen[0]["composition"] == {
        "mode": "prompt", "prompt": prompt, "analysis_direction": None,
    }
    brief = workflow_context.client.get(
        f"/api/v1/lyrics/versions/{task['versions'][0]['id']}/creation-brief",
        headers=_headers(workflow_context),
    ).json()
    assert brief["genre_tags"] == ["民谣"]
    assert brief["tempo"] == "slow"


def test_analysis_composition_uses_server_snapshot_and_no_invented_user_memory(workflow_context):
    assert _collect_sample(workflow_context, date.today()).status_code == 201
    analysis = workflow_context.client.post(
        "/api/v1/analysis/tasks", headers=_headers(workflow_context),
        json={"entry_ids": [], "window_days": 7},
    ).json()
    report = analysis["report"]
    selected = report["creation_directions"][1]
    with next(workflow_context.client.app.dependency_overrides[get_db]()) as db:
        stored = db.get(AnalysisReport, report["id"])
        raw_directions = deepcopy(stored.creation_directions)
        raw_directions[1]["tempo"] = "medium-fast"
        raw_directions[1]["vocal_gender"] = "不限"
        stored.creation_directions = raw_directions
        db.commit()
    selected["tempo"] = "fast"
    selected["vocal_gender"] = "unspecified"
    response = _post(workflow_context, {
        "mode": "analysis", "analysis_report_id": report["id"], "direction_index": 1,
    })
    assert response.status_code == 201, response.text
    task = response.json()
    assert task["genre_tags"] == selected["genre_tags"]
    assert task["keywords"] == selected["theme_keywords"]
    assert task["tempo"] == "fast"
    assert task["versions"][0]["title"] != selected["name"]
    assert _essences(workflow_context)["total"] == 0

    with next(workflow_context.client.app.dependency_overrides[get_db]()) as db:
        stored = db.get(LyricsTask, task["id"])
        assert stored.creation_input["analysis_direction"] == selected
        db.get(AnalysisReport, report["id"]).creation_directions = []
        db.commit()

    regenerated = workflow_context.client.post(
        f"/api/v1/lyrics/tasks/{task['id']}/regenerate", headers=_headers(workflow_context),
    )
    assert regenerated.status_code == 200, regenerated.text
    assert regenerated.json()["genre_tags"] == selected["genre_tags"]
    brief = workflow_context.client.get(
        f"/api/v1/lyrics/versions/{task['versions'][0]['id']}/creation-brief",
        headers=_headers(workflow_context),
    ).json()
    assert brief["instrument_tags"] == selected["instrument_tags"]
    assert brief["negative_constraints"] == selected["negative_constraints"]
    invalid = _post(workflow_context, {
        "mode": "analysis", "analysis_report_id": report["id"], "direction_index": 1,
    })
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "LYRICS_DIRECTION_NOT_FOUND"


def test_analysis_adjustment_is_transmitted_and_remembered(workflow_context):
    _collect_sample(workflow_context, date.today())
    report = workflow_context.client.post(
        "/api/v1/analysis/tasks", headers=_headers(workflow_context),
        json={"entry_ids": [], "window_days": 7},
    ).json()["report"]
    response = _post(workflow_context, {
        "mode": "analysis", "analysis_report_id": report["id"], "direction_index": 0,
        "prompt": "歌名《晚风》，副歌更口语化，不要苦情。",
    })
    assert response.status_code == 201, response.text
    assert response.json()["versions"][0]["title"] == "晚风"
    assert _essences(workflow_context)["total"] == 1


def test_missing_analysis_is_explicit(workflow_context):
    response = _post(workflow_context, {
        "mode": "analysis", "analysis_report_id": 9999, "direction_index": 0,
    })
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "LYRICS_ANALYSIS_NOT_FOUND"

    _collect_sample(workflow_context, date.today())
    report = workflow_context.client.post(
        "/api/v1/analysis/tasks", headers=_headers(workflow_context),
        json={"entry_ids": [], "window_days": 7},
    ).json()["report"]
    with next(workflow_context.client.app.dependency_overrides[get_db]()) as db:
        db.get(AnalysisReport, report["id"]).creation_directions = [{"name": "incomplete"}]
        db.commit()
    invalid = _post(workflow_context, {
        "mode": "analysis", "analysis_report_id": report["id"], "direction_index": 0,
    })
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "LYRICS_DIRECTION_INVALID"


def test_invalid_generated_features_fail_without_version_or_memory(workflow_context, monkeypatch):
    original = LocalTextProvider.generate_lyrics

    def incomplete(self, context, variation):
        result = original(self, {"theme": "成长"}, variation)
        return ProviderResult(output=result.output, call=result.call)

    monkeypatch.setattr(LocalTextProvider, "generate_lyrics", incomplete)
    response = _post(workflow_context, {"mode": "prompt", "prompt": "写一首成长的流行歌曲"})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "LYRICS_PROVIDER_FAILED"
    with next(workflow_context.client.app.dependency_overrides[get_db]()) as db:
        task = db.scalar(select(LyricsTask))
        assert task.status == "failed"
        assert task.versions == []
    history = workflow_context.client.get(
        "/api/v1/lyrics/tasks", headers=_headers(workflow_context),
    ).json()
    assert history["items"][0]["api_usage"][0]["status"] == "failed"
    assert _essences(workflow_context)["total"] == 0


def test_creation_input_migration_preserves_old_works():
    path = Path(__file__).parents[1] / "alembic/versions/c9b5d7e2a410_add_lyrics_creation_input.py"
    spec = spec_from_file_location("creation_input_migration", path)
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE lyrics_tasks (id INTEGER PRIMARY KEY, theme TEXT)"))
        connection.execute(text("INSERT INTO lyrics_tasks (id, theme) VALUES (1, 'original')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            row = connection.execute(text("SELECT theme, creation_input FROM lyrics_tasks")).one()
            assert row == ("original", None)
            migration.downgrade()
            assert connection.execute(text("SELECT theme FROM lyrics_tasks")).scalar_one() == "original"
    engine.dispose()
