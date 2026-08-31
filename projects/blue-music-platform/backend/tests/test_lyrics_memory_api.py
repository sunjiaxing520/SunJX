from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.config import settings
from app.core.security import hash_password
from app.main import create_app
from app.models import User, UserRole


class LyricsMemoryApiContext(NamedTuple):
    client: TestClient
    admin_token: str
    member_token: str


@pytest.fixture
def lyrics_memory_api_context(
    monkeypatch: pytest.MonkeyPatch,
) -> LyricsMemoryApiContext:
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
        db.add_all(
            [
                User(
                    username="admin",
                    password_hash=hash_password("admin-password"),
                    role=UserRole.SUPER_ADMIN,
                ),
                User(
                    username="member",
                    password_hash=hash_password("member-password"),
                    role=UserRole.MEMBER,
                ),
            ]
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
        admin_login = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin-password"},
        )
        member_login = client.post(
            "/api/v1/auth/login",
            json={"username": "member", "password": "member-password"},
        )
        yield LyricsMemoryApiContext(
            client,
            admin_login.json()["access_token"],
            member_login.json()["access_token"],
        )
    test_app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_admin_can_manage_rules_and_preview_hidden_memory(
    lyrics_memory_api_context: LyricsMemoryApiContext,
) -> None:
    context = lyrics_memory_api_context
    headers = _headers(context.admin_token)

    overview = context.client.get("/api/v1/lyrics-memory/overview", headers=headers)
    assert overview.status_code == 200
    assert overview.json()["total_events"] == 0

    created = context.client.post(
        "/api/v1/lyrics-memory/rules",
        headers=headers,
        json={
            "title": "副歌表达",
            "content": "副歌核心句应简短、直接，并保持原创表达。",
        },
    )
    assert created.status_code == 201
    event_id = created.json()["id"]
    assert created.json()["event_type"] == "admin_rule"

    preview = context.client.get("/api/v1/lyrics-memory/preview", headers=headers)
    assert preview.status_code == 200
    memory = preview.json()["memory"]
    assert memory["admin_rules"][0]["title"] == "副歌表达"
    assert "1_true_creation_requirements" in memory
    assert "5_ranking_lyrics_patterns" in memory

    events = context.client.get(
        "/api/v1/lyrics-memory/events",
        headers=headers,
        params={"event_type": "admin_rule"},
    )
    assert events.status_code == 200
    assert events.json()["total"] == 1
    assert events.json()["items"][0]["content_preview"].startswith("副歌核心句")

    detail = context.client.get(
        f"/api/v1/lyrics-memory/events/{event_id}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json()["context"]["title"] == "副歌表达"

    disabled = context.client.patch(
        f"/api/v1/lyrics-memory/events/{event_id}/usefulness",
        headers=headers,
        json={"is_useful": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["is_useful"] is False
    preview = context.client.get("/api/v1/lyrics-memory/preview", headers=headers)
    assert preview.json()["memory"]["admin_rules"] == []

    restored = context.client.patch(
        f"/api/v1/lyrics-memory/events/{event_id}/usefulness",
        headers=headers,
        json={"is_useful": True},
    )
    assert restored.status_code == 200

    deleted = context.client.request(
        "DELETE",
        "/api/v1/lyrics-memory/events",
        headers=headers,
        json={"event_ids": [event_id]},
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted_event_ids"] == [event_id]


def test_member_cannot_access_lyrics_memory_admin_api(
    lyrics_memory_api_context: LyricsMemoryApiContext,
) -> None:
    response = lyrics_memory_api_context.client.get(
        "/api/v1/lyrics-memory/overview",
        headers=_headers(lyrics_memory_api_context.member_token),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/v1/lyrics-memory/rules", {"title": "  ", "content": "有效规则"}),
        ("/api/v1/lyrics-memory/chat", {"instruction": "  "}),
        ("/api/v1/lyrics-memory/snapshots", {"name": "  "}),
    ],
)
def test_admin_memory_inputs_reject_whitespace_only_values(
    lyrics_memory_api_context: LyricsMemoryApiContext,
    path: str,
    payload: dict[str, str],
) -> None:
    response = lyrics_memory_api_context.client.post(
        path,
        headers=_headers(lyrics_memory_api_context.admin_token),
        json=payload,
    )

    assert response.status_code == 422


def test_admin_chat_changes_memory_only_after_confirmation(
    lyrics_memory_api_context: LyricsMemoryApiContext,
) -> None:
    context = lyrics_memory_api_context
    headers = _headers(context.admin_token)

    preview = context.client.post(
        "/api/v1/lyrics-memory/chat",
        headers=headers,
        json={"instruction": "以后副歌核心句尽量更短，避免解释性长句。"},
    )
    assert preview.status_code == 201
    proposal = preview.json()
    assert proposal["role"] == "assistant"
    assert proposal["is_applied"] is False
    assert proposal["proposal"]["operations"][0]["action"] == "add_rule"

    before_apply = context.client.get(
        "/api/v1/lyrics-memory/preview",
        headers=headers,
    ).json()
    assert before_apply["memory"]["admin_rules"] == []

    applied = context.client.post(
        f"/api/v1/lyrics-memory/chat/{proposal['id']}/apply",
        headers=headers,
    )
    assert applied.status_code == 200
    assert len(applied.json()["created_event_ids"]) == 1

    after_apply = context.client.get(
        "/api/v1/lyrics-memory/preview",
        headers=headers,
    ).json()
    assert after_apply["memory"]["admin_rules"][0]["rule"].startswith("以后副歌")

    repeated = context.client.post(
        f"/api/v1/lyrics-memory/chat/{proposal['id']}/apply",
        headers=headers,
    )
    assert repeated.status_code == 409

    history = context.client.get("/api/v1/lyrics-memory/chat", headers=headers)
    assert history.status_code == 200
    assert [item["role"] for item in history.json()["items"]] == [
        "user",
        "assistant",
    ]


def test_memory_snapshots_are_named_browsable_and_limited_to_twenty(
    lyrics_memory_api_context: LyricsMemoryApiContext,
) -> None:
    context = lyrics_memory_api_context
    headers = _headers(context.admin_token)

    created_ids: list[int] = []
    for index in range(20):
        response = context.client.post(
            "/api/v1/lyrics-memory/snapshots",
            headers=headers,
            json={"name": f"保留记忆 {index + 1}"},
        )
        assert response.status_code == 201
        created_ids.append(response.json()["id"])

    overflow = context.client.post(
        "/api/v1/lyrics-memory/snapshots",
        headers=headers,
        json={"name": "第 21 份"},
    )
    assert overflow.status_code == 409
    assert overflow.json()["error"]["code"] == "LYRICS_MEMORY_SNAPSHOT_LIMIT"

    listing = context.client.get("/api/v1/lyrics-memory/snapshots", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 20
    assert listing.json()["limit"] == 20

    snapshot_id = created_ids[0]
    detail = context.client.get(
        f"/api/v1/lyrics-memory/snapshots/{snapshot_id}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert "1_true_creation_requirements" in detail.json()["memory"]

    renamed = context.client.put(
        f"/api/v1/lyrics-memory/snapshots/{snapshot_id}",
        headers=headers,
        json={"name": "首轮客户偏好"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "首轮客户偏好"

    deleted = context.client.delete(
        f"/api/v1/lyrics-memory/snapshots/{snapshot_id}",
        headers=headers,
    )
    assert deleted.status_code == 204
    replacement = context.client.post(
        "/api/v1/lyrics-memory/snapshots",
        headers=headers,
        json={"name": "释放位置后新增"},
    )
    assert replacement.status_code == 201
