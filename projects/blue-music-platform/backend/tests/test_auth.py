from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, NamedTuple

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.cli.create_superadmin as create_superadmin_cli
import app.cli.diagnose as diagnose_cli
from app.api.dependencies import require_agent_permission
from app.cli.diagnose import _safe_database_url
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import hash_password, validate_security_settings, verify_password
from app.main import create_app
from app.models import AgentType, User, UserRole


class AuthContext(NamedTuple):
    client: TestClient
    session_factory: sessionmaker[Session]
    admin_id: int


@pytest.fixture
def auth_context() -> AuthContext:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
    )
    Base.metadata.create_all(bind=engine)

    with testing_session() as db:
        admin = User(
            username="admin",
            password_hash=hash_password("admin-password"),
            role=UserRole.SUPER_ADMIN,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        admin_id = admin.id

    test_app = create_app()

    def override_get_db():
        db = testing_session()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = override_get_db
    CrawlerUser = Annotated[
        User,
        Depends(require_agent_permission(AgentType.CRAWLER)),
    ]

    @test_app.get("/test/crawler")
    def crawler_test_endpoint(current_user: CrawlerUser) -> dict[str, int]:
        return {"user_id": current_user.id}

    with TestClient(test_app) as client:
        yield AuthContext(client, testing_session, admin_id)

    test_app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_member(client: TestClient, admin_token: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/users",
        headers=_authorization(admin_token),
        json={"username": "member.one", "password": "member-password"},
    )
    assert response.status_code == 201
    return response.json()


def test_login_returns_token_and_password_is_hashed(
    auth_context: AuthContext,
) -> None:
    token = _login(auth_context.client, "admin", "admin-password")

    with auth_context.session_factory() as db:
        admin = db.get(User, auth_context.admin_id)
        assert admin is not None
        assert admin.password_hash != "admin-password"
        assert verify_password("admin-password", admin.password_hash)

    response = auth_context.client.get(
        "/api/v1/auth/me",
        headers=_authorization(token),
    )
    assert response.status_code == 200
    assert response.json()["role"] == "super_admin"


def test_wrong_and_unknown_credentials_return_same_error(
    auth_context: AuthContext,
) -> None:
    wrong_password = auth_context.client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )
    unknown_user = auth_context.client.post(
        "/api/v1/auth/login",
        json={"username": "unknown", "password": "wrong-password"},
    )

    assert wrong_password.status_code == 401
    assert unknown_user.status_code == 401
    assert wrong_password.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"
    assert unknown_user.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"
    assert wrong_password.json()["error"]["message"] == unknown_user.json()[
        "error"
    ]["message"]


def test_missing_invalid_and_expired_tokens_are_rejected(
    auth_context: AuthContext,
) -> None:
    missing = auth_context.client.get("/api/v1/auth/me")
    invalid = auth_context.client.get(
        "/api/v1/auth/me",
        headers=_authorization("not-a-jwt"),
    )
    expired_token = jwt.encode(
        {
            "sub": str(auth_context.admin_id),
            "type": "access",
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        },
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    expired = auth_context.client.get(
        "/api/v1/auth/me",
        headers=_authorization(expired_token),
    )

    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "AUTH_TOKEN_MISSING"
    assert invalid.status_code == 401
    assert invalid.json()["error"]["code"] == "AUTH_TOKEN_INVALID"
    assert expired.status_code == 401
    assert expired.json()["error"]["code"] == "AUTH_TOKEN_EXPIRED"
    assert missing.headers["WWW-Authenticate"] == "Bearer"


def test_member_cannot_use_admin_endpoints(auth_context: AuthContext) -> None:
    admin_token = _login(auth_context.client, "admin", "admin-password")
    _create_member(auth_context.client, admin_token)
    member_token = _login(
        auth_context.client,
        "member.one",
        "member-password",
    )

    response = auth_context.client.get(
        "/api/v1/users",
        headers=_authorization(member_token),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_admin_manages_member_permissions_status_and_password(
    auth_context: AuthContext,
) -> None:
    admin_token = _login(auth_context.client, "admin", "admin-password")
    member = _create_member(auth_context.client, admin_token)
    member_id = int(member["id"])
    member_token = _login(
        auth_context.client,
        "member.one",
        "member-password",
    )

    denied = auth_context.client.get(
        "/test/crawler",
        headers=_authorization(member_token),
    )
    permission_update = auth_context.client.put(
        f"/api/v1/users/{member_id}/agent-permissions",
        headers=_authorization(admin_token),
        json={"agents": ["crawler", "lyrics"]},
    )
    allowed = auth_context.client.get(
        "/test/crawler",
        headers=_authorization(member_token),
    )
    password_reset = auth_context.client.put(
        f"/api/v1/users/{member_id}/password",
        headers=_authorization(admin_token),
        json={"password": "new-member-password"},
    )

    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "AGENT_PERMISSION_DENIED"
    assert permission_update.status_code == 200
    assert permission_update.json()["agent_permissions"] == [
        "crawler",
        "lyrics",
    ]
    assert allowed.status_code == 200
    assert password_reset.status_code == 204
    revoked = auth_context.client.get(
        "/api/v1/auth/me",
        headers=_authorization(member_token),
    )
    assert revoked.status_code == 401
    assert revoked.json()["error"]["code"] == "AUTH_TOKEN_REVOKED"
    _login(auth_context.client, "member.one", "new-member-password")

    deactivated = auth_context.client.patch(
        f"/api/v1/users/{member_id}/status",
        headers=_authorization(admin_token),
        json={"is_active": False},
    )
    blocked = auth_context.client.get(
        "/api/v1/auth/me",
        headers=_authorization(member_token),
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "USER_INACTIVE"


def test_duplicate_username_and_self_disable_are_rejected(
    auth_context: AuthContext,
) -> None:
    admin_token = _login(auth_context.client, "admin", "admin-password")
    _create_member(auth_context.client, admin_token)
    duplicate = auth_context.client.post(
        "/api/v1/users",
        headers=_authorization(admin_token),
        json={"username": "MEMBER.ONE", "password": "another-password"},
    )
    self_disable = auth_context.client.patch(
        f"/api/v1/users/{auth_context.admin_id}/status",
        headers=_authorization(admin_token),
        json={"is_active": False},
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "USERNAME_ALREADY_EXISTS"
    assert self_disable.status_code == 409
    assert self_disable.json()["error"]["code"] == "CANNOT_DISABLE_SELF"


def test_superadmin_initializer_is_idempotent_and_never_stores_plaintext(
    auth_context: AuthContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        create_superadmin_cli,
        "SessionLocal",
        auth_context.session_factory,
    )

    created = create_superadmin_cli.create_superadmin(
        "root.admin",
        "root-password",
    )
    repeated = create_superadmin_cli.create_superadmin(
        "root.admin",
        "different-password",
    )

    assert created["status"] == "created"
    assert repeated["status"] == "exists"
    with auth_context.session_factory() as db:
        user = db.scalar(select(User).where(User.username == "root.admin"))
        assert user is not None
        assert user.role == UserRole.SUPER_ADMIN
        assert user.password_hash != "root-password"
        assert verify_password("root-password", user.password_hash)


def test_production_rejects_unsafe_secret_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(
        settings,
        "SECRET_KEY",
        "dev_secret_key_change_in_production",
    )

    with pytest.raises(RuntimeError, match="Production SECRET_KEY"):
        validate_security_settings()


def test_diagnostic_database_url_hides_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "DATABASE_URL",
        "postgresql://diagnostic-user:very-secret@db:5432/music",
    )

    safe_url = _safe_database_url()

    assert "very-secret" not in safe_url
    assert "***" in safe_url


def test_diagnostic_reports_invalid_redis_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "REDIS_URL", "not-a-redis-url")

    result = diagnose_cli._redis_check()

    assert result["status"] == "error"
    assert "error_type" in result


def test_diagnostic_reports_broken_migration_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(diagnose_cli, "BACKEND_ROOT", tmp_path)

    result = diagnose_cli._migration_check(current_revision=None)

    assert result["status"] == "error"
    assert "error_type" in result


def test_openapi_documents_bearer_authentication() -> None:
    schema = create_app().openapi()

    assert schema["components"]["securitySchemes"]["HTTPBearer"] == {
        "type": "http",
        "scheme": "bearer",
    }
    assert "security" not in schema["paths"]["/api/v1/auth/login"]["post"]
    assert schema["paths"]["/api/v1/auth/me"]["get"]["security"] == [
        {"HTTPBearer": []}
    ]
    assert schema["paths"]["/api/v1/users"]["get"]["security"] == [
        {"HTTPBearer": []}
    ]
