from datetime import date, timedelta
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.adapters.kugou import parse_kugou_rank_page
from app.adapters.text_generation import LocalTextProvider, ProviderResult
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import create_app
from app.models import User, UserRole
from app.services.music_storage import StoredMusicObject
from tests.fakes import FakeSunoProvider


class WorkflowContext(NamedTuple):
    client: TestClient
    token: str


@pytest.fixture
def workflow_context(monkeypatch: pytest.MonkeyPatch) -> WorkflowContext:
    monkeypatch.setattr(settings, "AI_PROVIDER", "local")
    monkeypatch.setattr(settings, "AI_MODEL", "")
    monkeypatch.setattr(settings, "WORKFLOW_STEP_DELAY_SECONDS", 0)
    monkeypatch.setattr(settings, "MUSIC_QUEUE_MODE", "inline")
    monkeypatch.setattr(settings, "SUNO_PROVIDER_IMPLEMENTATION", "official")
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)
    with testing_session() as db:
        db.add(
            User(
                username="admin",
                password_hash=hash_password("admin-password"),
                role=UserRole.SUPER_ADMIN,
            )
        )
        db.commit()

    test_app = create_app()

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = override_get_db
    with TestClient(test_app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin-password"},
        )
        yield WorkflowContext(client, login.json()["access_token"])
    test_app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _headers(context: WorkflowContext) -> dict[str, str]:
    return {"Authorization": f"Bearer {context.token}"}


def _collect_sample(
    context: WorkflowContext,
    snapshot_date: date,
    *,
    chart: str = "top500",
    limit: int = 15,
):
    return context.client.post(
        "/api/v1/rankings/collections",
        headers=_headers(context),
        json={
            "source_mode": "sample",
            "chart": chart,
            "limit": limit,
            "snapshot_date": snapshot_date.isoformat(),
        },
    )


def _create_review_agent(
    context: WorkflowContext,
    name: str = "流程歌词审核官",
    *,
    pass_score: int = 80,
) -> dict:
    response = context.client.post(
        "/api/v1/review-agents",
        headers=_headers(context),
        json={
            "name": name,
            "pass_score": pass_score,
            "initialization_messages": [
                {
                    "role": "user",
                    "content": "严格审核歌词韵律、结构和可唱性，80 分及格。",
                }
            ],
        },
    )
    assert response.status_code == 201
    return response.json()


def test_kugou_page_parser_reads_structured_script_data() -> None:
    page = """
    <html><head><meta name="description" content="榜单更新于：2026-07-13"></head>
    <body><script>
    global.features = [{"Hash":"ABC","FileName":"歌手 - 歌名","timeLen":201,
    "album_id":12,"encrypt_id":"xyz","author_name":"歌手"}];
    </script></body></html>
    """

    result = parse_kugou_rank_page(page)

    assert result.source_updated_date == date(2026, 7, 13)
    assert result.items[0].title == "歌名"
    assert result.items[0].artist == "歌手"
    assert result.items[0].source_url == "https://www.kugou.com/mixsong/xyz.html"


def test_manual_lyrics_creation_rejects_chatter_before_creating_task(
    workflow_context: WorkflowContext,
) -> None:
    rejected = workflow_context.client.post(
        "/api/v1/lyrics/tasks",
        headers=_headers(workflow_context),
        json={"theme": "你好"},
    )

    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "LYRICS_PROMPT_IRRELEVANT"
    assert rejected.json()["error"]["detail"] == {"field": "歌曲主题"}

    tasks = workflow_context.client.get(
        "/api/v1/lyrics/tasks",
        headers=_headers(workflow_context),
    )
    assert tasks.status_code == 200
    assert tasks.json()["total"] == 0


def test_workflow_template_rejects_chatter_in_lyrics_configuration(
    workflow_context: WorkflowContext,
) -> None:
    rejected = workflow_context.client.post(
        "/api/v1/workflows/templates",
        headers=_headers(workflow_context),
        json={
            "name": "闲聊污染测试",
            "steps": ["analysis", "lyrics"],
            "configuration": {
                "analysis": {"window_days": 7},
                "lyrics": {"requirements": "今天天气怎么样"},
            },
        },
    )

    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "LYRICS_PROMPT_IRRELEVANT"
    assert rejected.json()["error"]["detail"] == {
        "field": "自动流程作词要求"
    }


def test_rising_chart_history_is_isolated_from_top500(
    workflow_context: WorkflowContext,
) -> None:
    yesterday = date.today() - timedelta(days=1)
    assert _collect_sample(workflow_context, yesterday, chart="top500").status_code == 201
    assert _collect_sample(workflow_context, date.today(), chart="top500").status_code == 201
    rising = _collect_sample(
        workflow_context,
        date.today(),
        chart="rising",
        limit=10,
    )
    assert rising.status_code == 201
    assert rising.json()["chart_code"] == "6666"

    snapshots = workflow_context.client.get(
        "/api/v1/rankings/snapshots",
        headers=_headers(workflow_context),
    ).json()
    rising_snapshot = next(
        snapshot for snapshot in snapshots if snapshot["id"] == rising.json()["snapshot_id"]
    )
    assert rising_snapshot["chart_name"]
    assert rising_snapshot["chart_code"] == "6666"

    entries = workflow_context.client.get(
        "/api/v1/rankings/entries",
        headers=_headers(workflow_context),
        params={"snapshot_id": rising_snapshot["id"], "page_size": 100},
    )
    assert entries.status_code == 200
    assert entries.json()["total"] == 10

    analysis = workflow_context.client.post(
        "/api/v1/analysis/tasks",
        headers=_headers(workflow_context),
        json={"entry_ids": [entries.json()["items"][0]["id"]], "window_days": 7},
    )
    assert analysis.status_code == 201
    assert analysis.json()["report"]["evidence"]["chart_code"] == "6666"
    assert analysis.json()["report"]["trend_metrics"]["available_days"] == 1


def test_analysis_can_select_an_earlier_chart_snapshot(
    workflow_context: WorkflowContext,
) -> None:
    today = date.today()
    rising = _collect_sample(workflow_context, today, chart="rising", limit=10)
    top500 = _collect_sample(workflow_context, today, chart="top500", limit=15)
    assert rising.status_code == 201
    assert top500.status_code == 201

    snapshots = workflow_context.client.get(
        "/api/v1/rankings/snapshots",
        headers=_headers(workflow_context),
        params={"limit": 100},
    ).json()
    assert snapshots[0]["id"] == top500.json()["snapshot_id"]

    analysis = workflow_context.client.post(
        "/api/v1/analysis/tasks",
        headers=_headers(workflow_context),
        json={
            "snapshot_id": rising.json()["snapshot_id"],
            "entry_ids": [],
            "window_days": 1,
        },
    )
    assert analysis.status_code == 201
    assert analysis.json()["selected_entry_count"] == 10
    assert analysis.json()["report"]["evidence"]["chart_code"] == "6666"

    refreshed_rising = _collect_sample(
        workflow_context,
        today,
        chart="rising",
        limit=10,
    )
    assert refreshed_rising.json()["snapshot_id"] == rising.json()["snapshot_id"]
    refreshed_snapshots = workflow_context.client.get(
        "/api/v1/rankings/snapshots",
        headers=_headers(workflow_context),
        params={"limit": 100},
    ).json()
    assert refreshed_snapshots[0]["id"] == rising.json()["snapshot_id"]


def test_collection_task_and_snapshot_have_stable_detail_routes(
    workflow_context: WorkflowContext,
) -> None:
    created = _collect_sample(workflow_context, date.today(), chart="rising", limit=10)
    assert created.status_code == 201
    task_id = created.json()["id"]
    snapshot_id = created.json()["snapshot_id"]

    task = workflow_context.client.get(
        f"/api/v1/rankings/collections/{task_id}",
        headers=_headers(workflow_context),
    )
    snapshot = workflow_context.client.get(
        f"/api/v1/rankings/snapshots/{snapshot_id}",
        headers=_headers(workflow_context),
    )
    assert task.status_code == 200
    assert task.json()["snapshot_id"] == snapshot_id
    assert snapshot.status_code == 200
    assert snapshot.json()["id"] == snapshot_id
    assert snapshot.json()["chart_code"] == "6666"

    deleted = workflow_context.client.delete(
        f"/api/v1/rankings/collections/{task_id}",
        headers=_headers(workflow_context),
    )
    assert deleted.status_code == 204
    missing_task = workflow_context.client.get(
        f"/api/v1/rankings/collections/{task_id}",
        headers=_headers(workflow_context),
    )
    preserved_snapshot = workflow_context.client.get(
        f"/api/v1/rankings/snapshots/{snapshot_id}",
        headers=_headers(workflow_context),
    )
    assert missing_task.status_code == 404
    assert missing_task.json()["error"]["code"] == "CRAWLER_TASK_NOT_FOUND"
    assert preserved_snapshot.status_code == 200

    missing_snapshot = workflow_context.client.get(
        "/api/v1/rankings/snapshots/999999",
        headers=_headers(workflow_context),
    )
    assert missing_snapshot.status_code == 404
    assert missing_snapshot.json()["error"]["code"] == "RANKING_SNAPSHOT_NOT_FOUND"


def test_workflow_rising_chart_analyzes_only_configured_rank(
    workflow_context: WorkflowContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_context: dict[str, object] = {}
    original_analyze = LocalTextProvider.analyze

    def capture_analysis(self, context):
        captured_context.update(context)
        return original_analyze(self, context)

    monkeypatch.setattr(LocalTextProvider, "analyze", capture_analysis)
    template = workflow_context.client.post(
        "/api/v1/workflows/templates",
        headers=_headers(workflow_context),
        json={
            "name": "Rising chart target analysis",
            "steps": ["collection", "analysis"],
            "configuration": {
                "collection": {
                    "source_mode": "sample",
                    "chart": "rising",
                    "limit": 1,
                    "rising_rank": 3,
                },
                "analysis": {"window_days": 30},
            },
        },
    )
    assert template.status_code == 201
    assert template.json()["configuration"]["collection"]["chart"] == "rising"
    assert template.json()["configuration"]["collection"]["rising_rank"] == 3

    started = workflow_context.client.post(
        f"/api/v1/workflows/templates/{template.json()['id']}/runs",
        headers=_headers(workflow_context),
    )
    assert started.status_code == 202
    run = workflow_context.client.get(
        f"/api/v1/workflows/runs/{started.json()['id']}",
        headers=_headers(workflow_context),
    ).json()
    collection_task_id = run["steps"][0]["task_id"]
    collection_tasks = workflow_context.client.get(
        "/api/v1/rankings/collections",
        headers=_headers(workflow_context),
    ).json()
    collection_task = next(task for task in collection_tasks if task["id"] == collection_task_id)
    assert collection_task["chart_code"] == "6666"
    assert collection_task["item_count"] == 3
    analysis = workflow_context.client.get(
        f"/api/v1/analysis/tasks/{run['steps'][1]['task_id']}",
        headers=_headers(workflow_context),
    ).json()
    assert analysis["selected_entry_count"] == 1
    assert analysis["window_days"] == 1
    assert captured_context["songs"][0]["latest_rank"] == 3


def test_daily_snapshots_analysis_and_lyrics_flow(
    workflow_context: WorkflowContext,
) -> None:
    yesterday = date.today() - timedelta(days=1)
    first = _collect_sample(workflow_context, yesterday)
    second = _collect_sample(workflow_context, date.today())
    rerun = _collect_sample(workflow_context, date.today())

    assert first.status_code == 201
    assert second.status_code == 201
    assert rerun.status_code == 201
    assert rerun.json()["status"] == "completed"
    assert rerun.json()["snapshot_id"] == second.json()["snapshot_id"]
    snapshots = workflow_context.client.get(
        "/api/v1/rankings/snapshots", headers=_headers(workflow_context)
    )
    assert len(snapshots.json()) == 2

    entries = workflow_context.client.get(
        "/api/v1/rankings/entries",
        headers=_headers(workflow_context),
        params={"page_size": 100},
    )
    assert entries.status_code == 200
    assert entries.json()["total"] == 15

    analysis = workflow_context.client.post(
        "/api/v1/analysis/tasks",
        headers=_headers(workflow_context),
        json={"entry_ids": [], "window_days": 7},
    )
    assert analysis.status_code == 201
    analysis_body = analysis.json()
    assert analysis_body["status"] == "completed"
    assert analysis_body["api_usage"][0]["endpoint"] == "local://rules-v1/analysis"
    assert analysis_body["api_usage"][0]["is_external"] is False
    assert analysis_body["api_usage"][0]["total_tokens"] == 0
    assert analysis_body["report"]["trend_metrics"]["available_days"] == 2
    assert len(analysis_body["report"]["creation_directions"]) == 3

    lyrics = workflow_context.client.post(
        "/api/v1/lyrics/tasks",
        headers=_headers(workflow_context),
        json={
            "analysis_report_id": analysis_body["report"]["id"],
            "direction_index": 0,
            "title_hint": "向光成长",
            "theme": "在成长中学会告别",
        },
    )
    assert lyrics.status_code == 201
    lyrics_body = lyrics.json()
    assert lyrics_body["status"] == "completed"
    assert lyrics_body["versions"][0]["title"] == "向光成长"
    assert "[Chorus1]" in lyrics_body["versions"][0]["content"]
    assert lyrics_body["versions"][0]["title"] in lyrics_body["versions"][0]["content"]

    regenerated = workflow_context.client.post(
        f"/api/v1/lyrics/tasks/{lyrics_body['id']}/regenerate",
        headers=_headers(workflow_context),
    )
    assert regenerated.status_code == 200
    assert len(regenerated.json()["versions"]) == 2
    assert len(regenerated.json()["api_usage"]) == 2
    version_id = regenerated.json()["versions"][1]["id"]

    saved = workflow_context.client.put(
        f"/api/v1/lyrics/versions/{version_id}/save",
        headers=_headers(workflow_context),
    )
    brief = workflow_context.client.get(
        f"/api/v1/lyrics/versions/{version_id}/creation-brief",
        headers=_headers(workflow_context),
    )
    assert saved.json()["is_saved"] is True
    assert brief.status_code == 200
    assert brief.json()["source_lyrics_version_id"] == version_id
    assert brief.json()["genre_tags"]

    analysis_favorite = workflow_context.client.post(
        "/api/v1/favorites",
        headers=_headers(workflow_context),
        json={"item_type": "analysis", "target_id": analysis_body["report"]["id"]},
    )
    lyrics_favorite = workflow_context.client.post(
        "/api/v1/favorites",
        headers=_headers(workflow_context),
        json={"item_type": "lyrics", "target_id": version_id},
    )
    duplicate = workflow_context.client.post(
        "/api/v1/favorites",
        headers=_headers(workflow_context),
        json={"item_type": "lyrics", "target_id": version_id},
    )
    assert analysis_favorite.status_code == 201
    assert lyrics_favorite.status_code == 201
    assert duplicate.json()["id"] == lyrics_favorite.json()["id"]
    assert lyrics_favorite.json()["metadata"]["version_number"] == 2
    assert lyrics_favorite.json()["created_by_username"] == "admin"

    note = workflow_context.client.patch(
        f"/api/v1/favorites/{lyrics_favorite.json()['id']}",
        headers=_headers(workflow_context),
        json={"note": "  副歌方向满意，后续优先制作  "},
    )
    assert note.status_code == 200
    assert note.json()["note"] == "副歌方向满意，后续优先制作"

    favorites = workflow_context.client.get(
        "/api/v1/favorites", headers=_headers(workflow_context)
    )
    assert favorites.status_code == 200
    assert favorites.json()["total"] == 2
    assert {item["item_type"] for item in favorites.json()["items"]} == {
        "analysis",
        "lyrics",
    }

    removed = workflow_context.client.delete(
        f"/api/v1/favorites/{analysis_favorite.json()['id']}",
        headers=_headers(workflow_context),
    )
    assert removed.status_code == 204
    analysis_favorites = workflow_context.client.get(
        "/api/v1/favorites",
        headers=_headers(workflow_context),
        params={"item_type": "analysis"},
    )
    assert analysis_favorites.json()["total"] == 0

    missing_target = workflow_context.client.post(
        "/api/v1/favorites",
        headers=_headers(workflow_context),
        json={"item_type": "lyrics", "target_id": 999999},
    )
    missing_favorite = workflow_context.client.patch(
        "/api/v1/favorites/999999",
        headers=_headers(workflow_context),
        json={"note": "不存在"},
    )
    assert missing_target.status_code == 404
    assert missing_target.json()["error"]["code"] == "FAVORITE_TARGET_NOT_FOUND"
    assert missing_favorite.status_code == 404
    assert missing_favorite.json()["error"]["code"] == "FAVORITE_NOT_FOUND"

    dashboard = workflow_context.client.get(
        "/api/v1/dashboard", headers=_headers(workflow_context)
    )
    usage = dashboard.json()["api_usage"]
    assert dashboard.status_code == 200
    assert usage["metrics"]["executions_today"] == 3
    assert usage["metrics"]["external_calls_today"] == 0
    assert usage["metrics"]["tokens_today"] == 0
    assert usage["providers"][0]["balance_status"] == "not_applicable"


def test_analysis_requires_ranking_data(workflow_context: WorkflowContext) -> None:
    response = workflow_context.client.post(
        "/api/v1/analysis/tasks",
        headers=_headers(workflow_context),
        json={"entry_ids": [], "window_days": 7},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ANALYSIS_NO_RANKING_DATA"


def test_live_collection_rejects_historical_snapshot_date(
    workflow_context: WorkflowContext,
) -> None:
    response = workflow_context.client.post(
        "/api/v1/rankings/collections",
        headers=_headers(workflow_context),
        json={
            "source_mode": "live",
            "limit": 10,
            "snapshot_date": (date.today() - timedelta(days=1)).isoformat(),
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CRAWLER_INVALID_SNAPSHOT_DATE"


def test_retention_uses_today_when_collecting_historical_sample(
    workflow_context: WorkflowContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    two_days_ago = date.today() - timedelta(days=2)
    yesterday = date.today() - timedelta(days=1)
    assert _collect_sample(workflow_context, two_days_ago).status_code == 201
    monkeypatch.setattr(settings, "RANKING_RETENTION_DAYS", 2)

    assert _collect_sample(workflow_context, yesterday).status_code == 201

    snapshots = workflow_context.client.get(
        "/api/v1/rankings/snapshots", headers=_headers(workflow_context)
    )
    assert snapshots.status_code == 200
    assert [item["snapshot_date"] for item in snapshots.json()] == [
        yesterday.isoformat()
    ]


def test_configurable_workflow_runs_collection_analysis_and_lyrics(
    workflow_context: WorkflowContext,
) -> None:
    created = workflow_context.client.post(
        "/api/v1/workflows/templates",
        headers=_headers(workflow_context),
        json={
            "name": "完整创作流程",
            "steps": ["collection", "analysis", "lyrics"],
            "configuration": {
                "collection": {"source_mode": "sample", "limit": 15},
                "analysis": {"window_days": 7},
                "lyrics": {
                    "direction_index": 2,
                    "theme": "根据榜单趋势完成一首成长主题歌曲",
                    "language": "中文",
                },
            },
        },
    )

    assert created.status_code == 201
    template = created.json()
    assert template["steps"] == ["collection", "analysis", "lyrics"]
    assert template["configuration"]["lyrics"]["direction_index"] == 2

    started = workflow_context.client.post(
        f"/api/v1/workflows/templates/{template['id']}/runs",
        headers=_headers(workflow_context),
    )

    assert started.status_code == 202
    run_id = started.json()["id"]
    detail = workflow_context.client.get(
        f"/api/v1/workflows/runs/{run_id}",
        headers=_headers(workflow_context),
    )
    assert detail.status_code == 200
    run = detail.json()
    assert run["status"] == "completed"
    assert run["current_step"] is None
    assert [step["step_type"] for step in run["steps"]] == [
        "collection",
        "analysis",
        "lyrics",
    ]
    assert {step["status"] for step in run["steps"]} == {"completed"}
    assert all(step["task_id"] for step in run["steps"])
    assert all(step["output_id"] for step in run["steps"])

    collection_step, analysis_step, lyrics_step = run["steps"]
    collections = workflow_context.client.get(
        "/api/v1/rankings/collections",
        headers=_headers(workflow_context),
    )
    collection_task = next(
        item
        for item in collections.json()
        if item["id"] == collection_step["task_id"]
    )
    assert collection_task["snapshot_id"] == collection_step["output_id"]

    analysis = workflow_context.client.get(
        f"/api/v1/analysis/tasks/{analysis_step['task_id']}",
        headers=_headers(workflow_context),
    )
    assert analysis.status_code == 200
    assert analysis.json()["selected_entry_count"] == 15
    assert analysis.json()["report"]["id"] == analysis_step["output_id"]

    lyrics_task_id = run["steps"][2]["task_id"]
    lyrics = workflow_context.client.get(
        f"/api/v1/lyrics/tasks/{lyrics_task_id}",
        headers=_headers(workflow_context),
    )
    assert lyrics.status_code == 200
    assert lyrics.json()["analysis_report_id"] == analysis_step["output_id"]
    assert lyrics.json()["direction_index"] == 0
    assert lyrics.json()["versions"]
    assert lyrics.json()["versions"][0]["id"] == lyrics_step["output_id"]


def test_workflow_passes_lyrics_output_into_suno_music(
    workflow_context: WorkflowContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FakeSunoProvider()
    monkeypatch.setattr(
        "app.services.music.get_music_provider",
        lambda *_args, **_kwargs: provider,
    )
    monkeypatch.setattr(
        "app.services.music._archive_audio",
        lambda *_args, **_kwargs: StoredMusicObject(
            backend="local",
            key="workflow/test.mp3",
        ),
    )
    created = workflow_context.client.post(
        "/api/v1/workflows/templates",
        headers=_headers(workflow_context),
        json={
            "name": "Suno 完整创作流程",
            "steps": ["collection", "analysis", "lyrics", "music"],
            "configuration": {
                "collection": {"source_mode": "sample", "limit": 15},
                "analysis": {"window_days": 7},
                "lyrics": {"direction_index": 0, "theme": "夏夜归途"},
                "music": {"title": "夏夜归途", "style_prompt": "温暖流行"},
            },
        },
    )
    assert created.status_code == 201

    started = workflow_context.client.post(
        f"/api/v1/workflows/templates/{created.json()['id']}/runs",
        headers=_headers(workflow_context),
    )
    run = workflow_context.client.get(
        f"/api/v1/workflows/runs/{started.json()['id']}",
        headers=_headers(workflow_context),
    ).json()

    assert run["status"] == "completed"
    assert [step["step_type"] for step in run["steps"]] == [
        "collection",
        "analysis",
        "lyrics",
        "music",
    ]
    lyrics_step = run["steps"][2]
    music_step = run["steps"][3]
    music = workflow_context.client.get(
        f"/api/v1/music/tasks/{music_step['task_id']}",
        headers=_headers(workflow_context),
    ).json()
    assert music["lyrics_version_id"] == lyrics_step["output_id"]
    assert music["results"][0]["id"] == music_step["output_id"]
    assert provider.generated[0].lyrics == music["lyrics"]


def test_reference_creation_searches_song_and_runs_complete_default_flow(
    workflow_context: WorkflowContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FakeSunoProvider()
    monkeypatch.setattr(
        "app.services.music.get_music_provider",
        lambda *_args, **_kwargs: provider,
    )
    monkeypatch.setattr(
        "app.services.music._archive_audio",
        lambda *_args, **_kwargs: StoredMusicObject(
            backend="local",
            key="workflow/reference.mp3",
        ),
    )
    collected = _collect_sample(workflow_context, date.today(), limit=8)
    assert collected.status_code == 201
    entries = workflow_context.client.get(
        "/api/v1/rankings/entries",
        headers=_headers(workflow_context),
        params={"snapshot_id": collected.json()["snapshot_id"], "page_size": 20},
    ).json()["items"]
    source = entries[0]

    search = workflow_context.client.get(
        "/api/v1/music/reference-songs",
        headers=_headers(workflow_context),
        params={"query": source["title"], "limit": 10},
    )
    assert search.status_code == 200
    assert search.json()["items"][0]["entry_id"] == source["id"]

    started = workflow_context.client.post(
        "/api/v1/music/reference-runs",
        headers=_headers(workflow_context),
        json={"source_entry_id": source["id"], "instruction": ""},
    )
    assert started.status_code == 202
    run = workflow_context.client.get(
        f"/api/v1/workflows/runs/{started.json()['id']}",
        headers=_headers(workflow_context),
    ).json()

    assert run["status"] == "completed"
    assert run["template_id"] is None
    assert run["configuration"]["reference"] == {
        "source_entry_id": source["id"],
        "instruction": None,
    }
    assert [step["step_type"] for step in run["steps"]] == [
        "analysis",
        "lyrics",
        "music",
    ]
    analysis = workflow_context.client.get(
        f"/api/v1/analysis/tasks/{run['steps'][0]['task_id']}",
        headers=_headers(workflow_context),
    ).json()
    assert analysis["selected_entry_count"] == 1
    music = workflow_context.client.get(
        f"/api/v1/music/tasks/{run['steps'][2]['task_id']}",
        headers=_headers(workflow_context),
    ).json()
    assert "生成一首完整的新歌曲" in music["requirements"]
    assert music["results"][0]["id"] == run["steps"][2]["output_id"]
    assert provider.generated[0].lyrics == music["lyrics"]


def test_workflow_review_pauses_after_one_failed_review_and_can_continue(
    workflow_context: WorkflowContext,
) -> None:
    agent = _create_review_agent(workflow_context)
    template = workflow_context.client.post(
        "/api/v1/workflows/templates",
        headers=_headers(workflow_context),
        json={
            "name": "单次审核人工判断流程",
            "steps": ["collection", "analysis", "lyrics", "review"],
            "configuration": {
                "collection": {"source_mode": "sample", "limit": 15},
                "analysis": {"window_days": 7},
                "lyrics": {"direction_index": 0, "theme": "城市夜归人"},
                "review": {"agent_id": agent["id"]},
            },
        },
    )
    assert template.status_code == 201

    started = workflow_context.client.post(
        f"/api/v1/workflows/templates/{template.json()['id']}/runs",
        headers=_headers(workflow_context),
    )
    assert started.status_code == 202
    run_id = started.json()["id"]
    run = workflow_context.client.get(
        f"/api/v1/workflows/runs/{run_id}",
        headers=_headers(workflow_context),
    ).json()

    assert run["status"] == "paused"
    assert run["current_step"] == "review"
    assert run["error_code"] == "WORKFLOW_REVIEW_DECISION_REQUIRED"
    review_step = run["steps"][3]
    assert review_step["status"] == "paused"
    assert review_step["result_detail"]["latest_score"] == 78
    assert review_step["result_detail"]["pass_score"] == 80
    assert len(review_step["result_detail"]["cycles"][0]["rounds"]) == 1
    assert review_step["result_detail"]["cycles"][0]["rounds"][0]["score"] == 78
    assert review_step["result_detail"]["latest_deduction_reasons"]
    assert review_step["result_detail"]["latest_revision_suggestions"]

    lyrics = workflow_context.client.get(
        f"/api/v1/lyrics/tasks/{run['steps'][2]['task_id']}",
        headers=_headers(workflow_context),
    ).json()
    assert len(lyrics["versions"]) == 1
    assert review_step["output_id"] == lyrics["versions"][-1]["id"]
    reviews = workflow_context.client.get(
        f"/api/v1/review-agents/{agent['id']}/reviews",
        headers=_headers(workflow_context),
    ).json()
    assert reviews["total"] == 1

    blocked_start = workflow_context.client.post(
        f"/api/v1/workflows/templates/{template.json()['id']}/runs",
        headers=_headers(workflow_context),
    )
    blocked_delete = workflow_context.client.delete(
        f"/api/v1/workflows/runs/{run_id}",
        headers=_headers(workflow_context),
    )
    assert blocked_start.status_code == 409
    assert blocked_start.json()["error"]["code"] == "WORKFLOW_ALREADY_RUNNING"
    assert blocked_delete.status_code == 409

    accepted = workflow_context.client.post(
        f"/api/v1/workflows/runs/{run_id}/review-decision",
        headers=_headers(workflow_context),
        json={"action": "accept"},
    )
    assert accepted.status_code == 202
    completed = workflow_context.client.get(
        f"/api/v1/workflows/runs/{run_id}",
        headers=_headers(workflow_context),
    ).json()
    assert completed["status"] == "completed"
    assert completed["steps"][3]["status"] == "completed"
    assert completed["steps"][3]["result_detail"]["status"] == "accepted_by_user"


def test_workflow_uses_each_review_agents_current_pass_score(
    workflow_context: WorkflowContext,
) -> None:
    agent = _create_review_agent(
        workflow_context,
        "独立及格线审核官",
        pass_score=75,
    )
    assert agent["pass_score"] == 75
    template = workflow_context.client.post(
        "/api/v1/workflows/templates",
        headers=_headers(workflow_context),
        json={
            "name": "审核线跟随智能体",
            "steps": ["collection", "analysis", "lyrics", "review"],
            "configuration": {
                "collection": {"source_mode": "sample", "limit": 15},
                "analysis": {"window_days": 7},
                "lyrics": {"direction_index": 0, "theme": "清晨出发"},
                "review": {"agent_id": agent["id"]},
            },
        },
    ).json()

    first = workflow_context.client.post(
        f"/api/v1/workflows/templates/{template['id']}/runs",
        headers=_headers(workflow_context),
    ).json()
    first_run = workflow_context.client.get(
        f"/api/v1/workflows/runs/{first['id']}",
        headers=_headers(workflow_context),
    ).json()
    assert first_run["status"] == "completed"
    assert first_run["steps"][3]["result_detail"]["pass_score"] == 75

    updated = workflow_context.client.patch(
        f"/api/v1/review-agents/{agent['id']}/settings",
        headers=_headers(workflow_context),
        json={"pass_score": 85},
    )
    assert updated.status_code == 200
    assert updated.json()["pass_score"] == 85

    second = workflow_context.client.post(
        f"/api/v1/workflows/templates/{template['id']}/runs",
        headers=_headers(workflow_context),
    ).json()
    second_run = workflow_context.client.get(
        f"/api/v1/workflows/runs/{second['id']}",
        headers=_headers(workflow_context),
    ).json()
    assert second_run["status"] == "paused"
    assert second_run["steps"][3]["result_detail"]["pass_score"] == 85


def test_workflow_review_revises_then_passes_latest_lyrics_to_music(
    workflow_context: WorkflowContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = _create_review_agent(workflow_context, "两轮达标审核官")
    original_review = LocalTextProvider.review_lyrics
    scores = iter((70, 85))

    def staged_review(self, context):
        result = original_review(self, context)
        return ProviderResult(
            output=result.output.model_copy(update={"overall_score": next(scores)}),
            call=result.call,
        )

    monkeypatch.setattr(LocalTextProvider, "review_lyrics", staged_review)
    provider = FakeSunoProvider()
    monkeypatch.setattr(
        "app.services.music.get_music_provider",
        lambda *_args, **_kwargs: provider,
    )
    monkeypatch.setattr(
        "app.services.music._archive_audio",
        lambda *_args, **_kwargs: StoredMusicObject(
            backend="local",
            key="workflow/reviewed.mp3",
        ),
    )
    template = workflow_context.client.post(
        "/api/v1/workflows/templates",
        headers=_headers(workflow_context),
        json={
            "name": "审核通过后生成音乐",
            "steps": ["collection", "analysis", "lyrics", "review", "music"],
            "configuration": {
                "collection": {"source_mode": "sample", "limit": 15},
                "analysis": {"window_days": 7},
                "lyrics": {"direction_index": 0, "theme": "雨后启程"},
                "review": {"agent_id": agent["id"]},
                "music": {"title": "雨后启程", "style_prompt": "温暖流行"},
            },
        },
    )
    assert template.status_code == 201

    started = workflow_context.client.post(
        f"/api/v1/workflows/templates/{template.json()['id']}/runs",
        headers=_headers(workflow_context),
    )
    run_id = started.json()["id"]
    paused = workflow_context.client.get(
        f"/api/v1/workflows/runs/{run_id}",
        headers=_headers(workflow_context),
    ).json()
    assert paused["status"] == "paused"
    assert paused["steps"][3]["result_detail"]["latest_score"] == 70
    assert paused["steps"][4]["status"] == "pending"

    decision = workflow_context.client.post(
        f"/api/v1/workflows/runs/{run_id}/review-decision",
        headers=_headers(workflow_context),
        json={"action": "revise"},
    )
    assert decision.status_code == 202
    run = workflow_context.client.get(
        f"/api/v1/workflows/runs/{run_id}",
        headers=_headers(workflow_context),
    ).json()

    assert run["status"] == "completed"
    lyrics_step, review_step, music_step = run["steps"][2:]
    cycles = review_step["result_detail"]["cycles"]
    assert [cycle["rounds"][0]["score"] for cycle in cycles] == [70, 85]
    assert all(len(cycle["rounds"]) == 1 for cycle in cycles)
    assert cycles[0]["resolution"]["action"] == "revise"
    assert review_step["output_id"] != lyrics_step["output_id"]
    music = workflow_context.client.get(
        f"/api/v1/music/tasks/{music_step['task_id']}",
        headers=_headers(workflow_context),
    ).json()
    assert music["lyrics_version_id"] == review_step["output_id"]
    assert provider.generated[0].lyrics == music["lyrics"]


def test_paused_workflow_supports_requested_revision_and_regeneration(
    workflow_context: WorkflowContext,
) -> None:
    agent = _create_review_agent(workflow_context, "人工判断审核官")
    template = workflow_context.client.post(
        "/api/v1/workflows/templates",
        headers=_headers(workflow_context),
        json={
            "name": "暂停后修改与重生成",
            "steps": ["collection", "analysis", "lyrics", "review"],
            "configuration": {
                "collection": {"source_mode": "sample", "limit": 15},
                "analysis": {"window_days": 7},
                "lyrics": {"direction_index": 0, "theme": "重新出发"},
                "review": {"agent_id": agent["id"]},
            },
        },
    ).json()
    started = workflow_context.client.post(
        f"/api/v1/workflows/templates/{template['id']}/runs",
        headers=_headers(workflow_context),
    ).json()
    run_id = started["id"]

    revised = workflow_context.client.post(
        f"/api/v1/workflows/runs/{run_id}/review-decision",
        headers=_headers(workflow_context),
        json={"action": "revise"},
    )
    assert revised.status_code == 202
    after_revision = workflow_context.client.get(
        f"/api/v1/workflows/runs/{run_id}",
        headers=_headers(workflow_context),
    ).json()
    assert after_revision["status"] == "paused"
    revision_detail = after_revision["steps"][3]["result_detail"]
    assert len(revision_detail["cycles"]) == 2
    assert revision_detail["cycles"][0]["resolution"]["action"] == "revise"

    regenerated = workflow_context.client.post(
        f"/api/v1/workflows/runs/{run_id}/review-decision",
        headers=_headers(workflow_context),
        json={"action": "regenerate"},
    )
    assert regenerated.status_code == 202
    after_regeneration = workflow_context.client.get(
        f"/api/v1/workflows/runs/{run_id}",
        headers=_headers(workflow_context),
    ).json()
    assert after_regeneration["status"] == "paused"
    regeneration_detail = after_regeneration["steps"][3]["result_detail"]
    assert len(regeneration_detail["cycles"]) == 3
    assert regeneration_detail["cycles"][1]["resolution"]["action"] == "regenerate"

    accepted = workflow_context.client.post(
        f"/api/v1/workflows/runs/{run_id}/review-decision",
        headers=_headers(workflow_context),
        json={"action": "accept"},
    )
    assert accepted.status_code == 202
    completed = workflow_context.client.get(
        f"/api/v1/workflows/runs/{run_id}",
        headers=_headers(workflow_context),
    ).json()
    assert completed["status"] == "completed"


def test_workflow_stops_on_failed_step(
    workflow_context: WorkflowContext,
) -> None:
    created = workflow_context.client.post(
        "/api/v1/workflows/templates",
        headers=_headers(workflow_context),
        json={
            "name": "仅分析最新榜单",
            "steps": ["analysis"],
            "configuration": {"analysis": {"window_days": 7}},
        },
    )
    assert created.status_code == 201

    started = workflow_context.client.post(
        f"/api/v1/workflows/templates/{created.json()['id']}/runs",
        headers=_headers(workflow_context),
    )
    assert started.status_code == 202

    detail = workflow_context.client.get(
        f"/api/v1/workflows/runs/{started.json()['id']}",
        headers=_headers(workflow_context),
    )
    run = detail.json()
    assert run["status"] == "failed"
    assert run["error_code"] == "ANALYSIS_NO_RANKING_DATA"
    assert run["steps"][0]["status"] == "failed"
    assert run["steps"][0]["error_code"] == "ANALYSIS_NO_RANKING_DATA"


def test_workflow_rejects_lyrics_without_analysis(
    workflow_context: WorkflowContext,
) -> None:
    response = workflow_context.client.post(
        "/api/v1/workflows/templates",
        headers=_headers(workflow_context),
        json={"name": "无来源作词", "steps": ["lyrics"]},
    )

    assert response.status_code == 422


def test_delete_lyrics_task_cleans_outputs_and_preserves_usage_audit(
    workflow_context: WorkflowContext,
) -> None:
    template = workflow_context.client.post(
        "/api/v1/workflows/templates",
        headers=_headers(workflow_context),
        json={
            "name": "待删除产出流程",
            "steps": ["collection", "analysis", "lyrics"],
            "configuration": {
                "collection": {"source_mode": "sample", "limit": 15},
                "analysis": {"window_days": 7},
                "lyrics": {"direction_index": 0, "theme": "测试删除歌词产出"},
            },
        },
    )
    started = workflow_context.client.post(
        f"/api/v1/workflows/templates/{template.json()['id']}/runs",
        headers=_headers(workflow_context),
    )
    run_id = started.json()["id"]
    run = workflow_context.client.get(
        f"/api/v1/workflows/runs/{run_id}",
        headers=_headers(workflow_context),
    ).json()
    lyrics_step = run["steps"][-1]
    lyrics_task_id = lyrics_step["task_id"]
    lyrics_version_id = lyrics_step["output_id"]

    favorite = workflow_context.client.post(
        "/api/v1/favorites",
        headers=_headers(workflow_context),
        json={"item_type": "lyrics", "target_id": lyrics_version_id},
    )
    assert favorite.status_code == 201

    deleted = workflow_context.client.delete(
        f"/api/v1/lyrics/tasks/{lyrics_task_id}",
        headers=_headers(workflow_context),
    )

    assert deleted.status_code == 204
    missing = workflow_context.client.get(
        f"/api/v1/lyrics/tasks/{lyrics_task_id}",
        headers=_headers(workflow_context),
    )
    assert missing.status_code == 404
    favorites = workflow_context.client.get(
        "/api/v1/favorites",
        headers=_headers(workflow_context),
        params={"item_type": "lyrics"},
    )
    assert favorites.json()["total"] == 0

    updated_run = workflow_context.client.get(
        f"/api/v1/workflows/runs/{run_id}",
        headers=_headers(workflow_context),
    ).json()
    deleted_step = updated_run["steps"][-1]
    assert deleted_step["status"] == "completed"
    assert deleted_step["task_id"] is None
    assert deleted_step["output_id"] is None

    dashboard = workflow_context.client.get(
        "/api/v1/dashboard",
        headers=_headers(workflow_context),
    ).json()
    assert any(
        record["task_type"] == "lyrics" and record["task_id"] == lyrics_task_id
        for record in dashboard["api_usage"]["recent_calls"]
    )


def test_bulk_delete_lyrics_tasks_deduplicates_ids(
    workflow_context: WorkflowContext,
) -> None:
    task_ids = []
    for theme in ("第一条待删除歌词", "第二条待删除歌词"):
        created = workflow_context.client.post(
            "/api/v1/lyrics/tasks",
            headers=_headers(workflow_context),
            json={"theme": theme},
        )
        assert created.status_code == 201
        task_ids.append(created.json()["id"])

    deleted = workflow_context.client.request(
        "DELETE",
        "/api/v1/lyrics/tasks",
        headers=_headers(workflow_context),
        json={"task_ids": [task_ids[0], task_ids[0], task_ids[1]]},
    )

    assert deleted.status_code == 200
    assert deleted.json() == {
        "deleted_count": 2,
        "deleted_task_ids": task_ids,
    }
    history = workflow_context.client.get(
        "/api/v1/lyrics/tasks",
        headers=_headers(workflow_context),
    )
    assert history.json()["total"] == 0

    missing = workflow_context.client.delete(
        f"/api/v1/lyrics/tasks/{task_ids[0]}",
        headers=_headers(workflow_context),
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "LYRICS_TASK_NOT_FOUND"


def test_bulk_delete_analysis_cleans_report_links_and_preserves_lyrics(
    workflow_context: WorkflowContext,
) -> None:
    template = workflow_context.client.post(
        "/api/v1/workflows/templates",
        headers=_headers(workflow_context),
        json={
            "name": "待删除分析流程",
            "steps": ["collection", "analysis"],
            "configuration": {
                "collection": {"source_mode": "sample", "limit": 15},
                "analysis": {"window_days": 7},
            },
        },
    )
    started = workflow_context.client.post(
        f"/api/v1/workflows/templates/{template.json()['id']}/runs",
        headers=_headers(workflow_context),
    )
    run_id = started.json()["id"]
    run = workflow_context.client.get(
        f"/api/v1/workflows/runs/{run_id}",
        headers=_headers(workflow_context),
    ).json()
    analysis_step = run["steps"][-1]
    first_task_id = analysis_step["task_id"]
    first_report_id = analysis_step["output_id"]

    favorite = workflow_context.client.post(
        "/api/v1/favorites",
        headers=_headers(workflow_context),
        json={"item_type": "analysis", "target_id": first_report_id},
    )
    lyrics = workflow_context.client.post(
        "/api/v1/lyrics/tasks",
        headers=_headers(workflow_context),
        json={
            "analysis_report_id": first_report_id,
            "direction_index": 0,
            "theme": "保留歌词但删除来源分析",
        },
    )
    second = workflow_context.client.post(
        "/api/v1/analysis/tasks",
        headers=_headers(workflow_context),
        json={"entry_ids": [], "window_days": 7},
    )
    assert favorite.status_code == 201
    assert lyrics.status_code == 201
    assert second.status_code == 201
    second_task_id = second.json()["id"]

    deleted = workflow_context.client.request(
        "DELETE",
        "/api/v1/analysis/tasks",
        headers=_headers(workflow_context),
        json={"task_ids": [first_task_id, first_task_id, second_task_id]},
    )

    assert deleted.status_code == 200
    assert deleted.json() == {
        "deleted_count": 2,
        "deleted_task_ids": [first_task_id, second_task_id],
    }
    history = workflow_context.client.get(
        "/api/v1/analysis/tasks",
        headers=_headers(workflow_context),
    )
    assert history.json()["total"] == 0
    favorites = workflow_context.client.get(
        "/api/v1/favorites",
        headers=_headers(workflow_context),
        params={"item_type": "analysis"},
    )
    assert favorites.json()["total"] == 0

    preserved_lyrics = workflow_context.client.get(
        f"/api/v1/lyrics/tasks/{lyrics.json()['id']}",
        headers=_headers(workflow_context),
    ).json()
    assert preserved_lyrics["analysis_report_id"] is None
    assert preserved_lyrics["direction_index"] is None
    assert preserved_lyrics["versions"]

    updated_run = workflow_context.client.get(
        f"/api/v1/workflows/runs/{run_id}",
        headers=_headers(workflow_context),
    ).json()
    deleted_step = updated_run["steps"][-1]
    assert deleted_step["status"] == "completed"
    assert deleted_step["task_id"] is None
    assert deleted_step["output_id"] is None

    dashboard = workflow_context.client.get(
        "/api/v1/dashboard",
        headers=_headers(workflow_context),
    ).json()
    usage_task_ids = {
        record["task_id"]
        for record in dashboard["api_usage"]["recent_calls"]
        if record["task_type"] == "analysis"
    }
    assert {first_task_id, second_task_id}.issubset(usage_task_ids)

    missing = workflow_context.client.delete(
        f"/api/v1/analysis/tasks/{first_task_id}",
        headers=_headers(workflow_context),
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "ANALYSIS_TASK_NOT_FOUND"


def test_delete_collection_records_keeps_single_daily_snapshot(
    workflow_context: WorkflowContext,
) -> None:
    template = workflow_context.client.post(
        "/api/v1/workflows/templates",
        headers=_headers(workflow_context),
        json={
            "name": "仅采集待删除记录",
            "steps": ["collection"],
            "configuration": {
                "collection": {"source_mode": "sample", "limit": 15}
            },
        },
    )
    started = workflow_context.client.post(
        f"/api/v1/workflows/templates/{template.json()['id']}/runs",
        headers=_headers(workflow_context),
    )
    run_id = started.json()["id"]
    run = workflow_context.client.get(
        f"/api/v1/workflows/runs/{run_id}",
        headers=_headers(workflow_context),
    ).json()
    collection_step = run["steps"][0]
    first_task_id = collection_step["task_id"]
    snapshot_id = collection_step["output_id"]

    before = workflow_context.client.get(
        "/api/v1/rankings/snapshots",
        headers=_headers(workflow_context),
    ).json()
    second = _collect_sample(workflow_context, date.today())
    assert second.status_code == 201
    assert second.json()["snapshot_id"] == snapshot_id
    second_task_id = second.json()["id"]
    after = workflow_context.client.get(
        "/api/v1/rankings/snapshots",
        headers=_headers(workflow_context),
    ).json()
    assert len(before) == len(after) == 1
    assert after[0]["id"] == snapshot_id
    assert after[0]["collected_at"] >= before[0]["collected_at"]

    deleted = workflow_context.client.request(
        "DELETE",
        "/api/v1/rankings/collections",
        headers=_headers(workflow_context),
        json={"task_ids": [first_task_id, first_task_id, second_task_id]},
    )

    assert deleted.status_code == 200
    assert deleted.json() == {
        "deleted_count": 2,
        "deleted_task_ids": [first_task_id, second_task_id],
    }
    history = workflow_context.client.get(
        "/api/v1/rankings/collections",
        headers=_headers(workflow_context),
    )
    assert history.json() == []
    snapshots = workflow_context.client.get(
        "/api/v1/rankings/snapshots",
        headers=_headers(workflow_context),
    )
    assert [item["id"] for item in snapshots.json()] == [snapshot_id]
    entries = workflow_context.client.get(
        "/api/v1/rankings/entries",
        headers=_headers(workflow_context),
        params={"snapshot_id": snapshot_id, "page_size": 100},
    )
    assert entries.json()["total"] == 15

    updated_run = workflow_context.client.get(
        f"/api/v1/workflows/runs/{run_id}",
        headers=_headers(workflow_context),
    ).json()
    preserved_step = updated_run["steps"][0]
    assert preserved_step["status"] == "completed"
    assert preserved_step["task_id"] is None
    assert preserved_step["output_id"] == snapshot_id

    third = _collect_sample(workflow_context, date.today())
    single_deleted = workflow_context.client.delete(
        f"/api/v1/rankings/collections/{third.json()['id']}",
        headers=_headers(workflow_context),
    )
    assert single_deleted.status_code == 204
    assert workflow_context.client.get(
        "/api/v1/rankings/collections",
        headers=_headers(workflow_context),
    ).json() == []


def test_bulk_delete_workflow_runs_preserves_templates_and_step_outputs(
    workflow_context: WorkflowContext,
) -> None:
    template = workflow_context.client.post(
        "/api/v1/workflows/templates",
        headers=_headers(workflow_context),
        json={
            "name": "待清理运行记录流程",
            "steps": ["collection"],
            "configuration": {
                "collection": {"source_mode": "sample", "limit": 15}
            },
        },
    ).json()
    run_ids = []
    task_ids = []
    for _ in range(2):
        started = workflow_context.client.post(
            f"/api/v1/workflows/templates/{template['id']}/runs",
            headers=_headers(workflow_context),
        )
        assert started.status_code == 202
        run = workflow_context.client.get(
            f"/api/v1/workflows/runs/{started.json()['id']}",
            headers=_headers(workflow_context),
        ).json()
        assert run["status"] == "completed"
        run_ids.append(run["id"])
        task_ids.append(run["steps"][0]["task_id"])

    deleted = workflow_context.client.request(
        "DELETE",
        "/api/v1/workflows/runs",
        headers=_headers(workflow_context),
        json={"run_ids": [run_ids[0], run_ids[0], run_ids[1]]},
    )

    assert deleted.status_code == 200
    assert deleted.json() == {
        "deleted_count": 2,
        "deleted_run_ids": run_ids,
    }
    history = workflow_context.client.get(
        "/api/v1/workflows/runs",
        headers=_headers(workflow_context),
    )
    assert history.json()["total"] == 0
    templates = workflow_context.client.get(
        "/api/v1/workflows/templates",
        headers=_headers(workflow_context),
    )
    assert [item["id"] for item in templates.json()] == [template["id"]]
    collection_history = workflow_context.client.get(
        "/api/v1/rankings/collections",
        headers=_headers(workflow_context),
    ).json()
    assert {item["id"] for item in collection_history} == set(task_ids)

    missing = workflow_context.client.delete(
        f"/api/v1/workflows/runs/{run_ids[0]}",
        headers=_headers(workflow_context),
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "WORKFLOW_RUN_NOT_FOUND"


def test_running_workflow_run_cannot_be_deleted(
    workflow_context: WorkflowContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.v1.routes.workflows.execute_workflow_run",
        lambda *_args, **_kwargs: None,
    )
    template = workflow_context.client.post(
        "/api/v1/workflows/templates",
        headers=_headers(workflow_context),
        json={
            "name": "运行中不可删除流程",
            "steps": ["collection"],
            "configuration": {
                "collection": {"source_mode": "sample", "limit": 15}
            },
        },
    ).json()
    started = workflow_context.client.post(
        f"/api/v1/workflows/templates/{template['id']}/runs",
        headers=_headers(workflow_context),
    )
    run_id = started.json()["id"]

    deleted = workflow_context.client.delete(
        f"/api/v1/workflows/runs/{run_id}",
        headers=_headers(workflow_context),
    )

    assert deleted.status_code == 409
    assert deleted.json()["error"]["code"] == "WORKFLOW_RUN_DELETE_CONFLICT"
    assert deleted.json()["error"]["detail"]["active_run_ids"] == [run_id]
