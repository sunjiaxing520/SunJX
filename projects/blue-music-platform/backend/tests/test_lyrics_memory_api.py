from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
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


def test_admin_can_view_memory_and_configure_injection_limit(
    lyrics_memory_api_context: LyricsMemoryApiContext,
) -> None:
    context = lyrics_memory_api_context
    headers = _headers(context.admin_token)

    current = context.client.get("/api/v1/lyrics-memory", headers=headers)
    assert current.status_code == 200
    assert current.json()["items"] == []
    assert current.json()["injection_limit"] == 60

    updated = context.client.patch(
        "/api/v1/lyrics-memory/settings",
        headers=headers,
        json={"injection_limit": 24},
    )
    assert updated.status_code == 200
    assert updated.json()["injection_limit"] == 24


def test_admin_chat_applies_memory_change_immediately(
    lyrics_memory_api_context: LyricsMemoryApiContext,
) -> None:
    context = lyrics_memory_api_context
    headers = _headers(context.admin_token)

    changed = context.client.post(
        "/api/v1/lyrics-memory/chat",
        headers=headers,
        json={"instruction": "副歌核心句应简短直接，避免解释性长句。"},
    )
    assert changed.status_code == 201
    body = changed.json()
    assert body["message"]["role"] == "assistant"
    assert body["message"]["is_applied"] is True
    assert body["memory"]["items"][0]["category"] == "preference"
    assert "副歌核心句" in body["memory"]["items"][0]["content"]

    history = context.client.get("/api/v1/lyrics-memory/chat", headers=headers)
    assert history.status_code == 200
    assert [item["role"] for item in history.json()["items"]] == [
        "user",
        "assistant",
    ]


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", "/api/v1/lyrics-memory/chat", {"instruction": "  "}),
        ("patch", "/api/v1/lyrics-memory/settings", {"injection_limit": 201}),
    ],
)
def test_memory_inputs_are_validated(
    lyrics_memory_api_context: LyricsMemoryApiContext,
    method: str,
    path: str,
    payload: dict[str, object],
) -> None:
    response = getattr(lyrics_memory_api_context.client, method)(
        path,
        headers=_headers(lyrics_memory_api_context.admin_token),
        json=payload,
    )
    assert response.status_code == 422


def test_member_cannot_access_team_memory(
    lyrics_memory_api_context: LyricsMemoryApiContext,
) -> None:
    response = lyrics_memory_api_context.client.get(
        "/api/v1/lyrics-memory",
        headers=_headers(lyrics_memory_api_context.member_token),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"
