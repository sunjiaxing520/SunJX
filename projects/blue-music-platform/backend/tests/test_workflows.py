from datetime import date, timedelta
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.adapters.kugou import parse_kugou_rank_page
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import create_app
from app.models import User, UserRole


class WorkflowContext(NamedTuple):
    client: TestClient
    token: str


@pytest.fixture
def workflow_context(monkeypatch: pytest.MonkeyPatch) -> WorkflowContext:
    monkeypatch.setattr(settings, "AI_PROVIDER", "local")
    monkeypatch.setattr(settings, "AI_MODEL", "")
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


def _collect_sample(context: WorkflowContext, snapshot_date: date):
    return context.client.post(
        "/api/v1/rankings/collections",
        headers=_headers(context),
        json={
            "source_mode": "sample",
            "limit": 15,
            "snapshot_date": snapshot_date.isoformat(),
        },
    )


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
            "theme": "在成长中学会告别",
        },
    )
    assert lyrics.status_code == 201
    lyrics_body = lyrics.json()
    assert lyrics_body["status"] == "completed"
    assert "[Chorus]" in lyrics_body["versions"][0]["content"]
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
