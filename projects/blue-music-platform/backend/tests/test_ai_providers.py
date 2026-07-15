import json
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.adapters import text_generation
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.credential_crypto import decrypt_credential
from app.core.security import hash_password
from app.main import create_app
from app.models import AiProviderConfig, User, UserRole
from app.services.ai_providers import resolve_text_provider


class ProviderContext(NamedTuple):
    client: TestClient
    session_factory: sessionmaker[Session]
    admin_token: str
    member_token: str


class FakeProviderResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {
            "id": "provider-test-request",
            "choices": [
                {"message": {"content": json.dumps({"status": "ok"})}}
            ],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 4,
                "total_tokens": 16,
            },
        }


@pytest.fixture
def provider_context(monkeypatch: pytest.MonkeyPatch) -> ProviderContext:
    monkeypatch.setattr(settings, "AI_PROVIDER", "local")
    monkeypatch.setattr(settings, "AI_BASE_URL", "")
    monkeypatch.setattr(settings, "AI_API_KEY", "")
    monkeypatch.setattr(settings, "AI_MODEL", "")
    monkeypatch.setattr(
        settings,
        "AI_CONFIG_ENCRYPTION_KEY",
        "provider-test-encryption-key",
    )
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

    app = create_app()

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        admin_token = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin-password"},
        ).json()["access_token"]
        member_token = client.post(
            "/api/v1/auth/login",
            json={"username": "member", "password": "member-password"},
        ).json()["access_token"]
        yield ProviderContext(client, testing_session, admin_token, member_token)

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_provider_templates_and_management_are_admin_only(
    provider_context: ProviderContext,
) -> None:
    admin = provider_context.client.get(
        "/api/v1/ai-providers/templates",
        headers=_headers(provider_context.admin_token),
    )
    member = provider_context.client.get(
        "/api/v1/ai-providers/templates",
        headers=_headers(provider_context.member_token),
    )

    assert admin.status_code == 200
    assert {item["key"] for item in admin.json()} >= {
        "local",
        "bigmodel",
        "deepseek",
        "qwen",
        "minimax",
        "openai_compatible",
    }
    assert member.status_code == 403


def test_encrypted_config_can_be_tested_and_hot_switched(
    provider_context: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "test-provider-api-key"
    created = provider_context.client.post(
        "/api/v1/ai-providers",
        headers=_headers(provider_context.admin_token),
        json={
            "name": "智谱主账号",
            "template_key": "bigmodel",
            "model": "glm-4.7-flash",
            "api_key": secret,
        },
    )
    assert created.status_code == 201
    created_body = created.json()
    assert secret not in created.text
    assert created_body["api_key_hint"].endswith("-key")
    assert created_body["last_test_status"] == "untested"

    with provider_context.session_factory() as db:
        stored = db.scalar(
            select(AiProviderConfig).where(AiProviderConfig.name == "智谱主账号")
        )
        assert stored is not None
        assert stored.api_key_encrypted != secret
        assert decrypt_credential(stored.api_key_encrypted or "") == secret

    blocked = provider_context.client.post(
        f"/api/v1/ai-providers/{created_body['id']}/activate",
        headers=_headers(provider_context.admin_token),
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "AI_PROVIDER_TEST_REQUIRED"

    captured: dict[str, object] = {}

    def fake_post(*args, **kwargs):
        captured.update(kwargs.get("json") or {})
        return FakeProviderResponse()

    monkeypatch.setattr(text_generation.httpx, "post", fake_post)
    tested = provider_context.client.post(
        f"/api/v1/ai-providers/{created_body['id']}/test",
        headers=_headers(provider_context.admin_token),
    )
    assert tested.status_code == 200
    assert tested.json()["status"] == "success"
    assert tested.json()["api_usage"]["total_tokens"] == 16
    assert tested.json()["api_usage"]["provider"] == "bigmodel"
    assert captured["max_tokens"] == 32

    activated = provider_context.client.post(
        f"/api/v1/ai-providers/{created_body['id']}/activate",
        headers=_headers(provider_context.admin_token),
    )
    assert activated.status_code == 200
    assert activated.json()["is_active"] is True
    with provider_context.session_factory() as db:
        provider = resolve_text_provider(db)
        assert provider.name == "bigmodel"
        assert provider.model == "glm-4.7-flash"

    active_edit = provider_context.client.put(
        f"/api/v1/ai-providers/{created_body['id']}",
        headers=_headers(provider_context.admin_token),
        json={"model": "another-model"},
    )
    assert active_edit.status_code == 409

    local = provider_context.client.post(
        "/api/v1/ai-providers",
        headers=_headers(provider_context.admin_token),
        json={"name": "离线降级", "template_key": "local"},
    ).json()
    local_test = provider_context.client.post(
        f"/api/v1/ai-providers/{local['id']}/test",
        headers=_headers(provider_context.admin_token),
    )
    assert local_test.json()["status"] == "success"
    local_activation = provider_context.client.post(
        f"/api/v1/ai-providers/{local['id']}/activate",
        headers=_headers(provider_context.admin_token),
    )
    assert local_activation.json()["is_active"] is True

    listing = provider_context.client.get(
        "/api/v1/ai-providers",
        headers=_headers(provider_context.admin_token),
    ).json()
    assert listing["runtime_source"] == "database"
    assert sum(item["is_active"] for item in listing["items"]) == 1
    assert listing["items"][0]["template_key"] == "local"


def test_environment_import_never_returns_plaintext_key(
    provider_context: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "AI_PROVIDER", "openai_compatible")
    monkeypatch.setattr(
        settings,
        "AI_BASE_URL",
        "https://open.bigmodel.cn/api/paas/v4",
    )
    monkeypatch.setattr(settings, "AI_API_KEY", "environment-secret-key")
    monkeypatch.setattr(settings, "AI_MODEL", "glm-4.7-flash")

    imported = provider_context.client.post(
        "/api/v1/ai-providers/import-environment",
        headers=_headers(provider_context.admin_token),
    )

    assert imported.status_code == 200
    assert imported.json()["template_key"] == "bigmodel"
    assert imported.json()["source"] == "environment"
    assert "environment-secret-key" not in imported.text
