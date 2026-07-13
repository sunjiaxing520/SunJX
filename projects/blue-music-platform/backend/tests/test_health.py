from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import get_db
from app.main import app


class WorkingSession:
    def execute(self, statement: object) -> None:
        return None


class FailingSession:
    def execute(self, statement: object) -> None:
        raise SQLAlchemyError("database unavailable")


def test_root_returns_running_message(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert len(response.headers["X-Request-ID"]) == 32
    assert response.json() == {
        "status": "ok",
        "message": "蓝乐 AI 音乐创作平台运行中",
    }


def test_health_returns_service_metadata(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "version": "0.1.0",
        "service": "blue-music-platform",
        "environment": "development",
    }


def test_database_health_returns_healthy_when_query_succeeds(
    client: TestClient,
) -> None:
    def override_get_db():
        yield WorkingSession()

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get("/api/v1/health/database")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "database": "postgresql",
        "detail": "database connection is available",
    }


def test_database_health_returns_503_when_query_fails(
    client: TestClient,
) -> None:
    def override_get_db():
        yield FailingSession()

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get("/api/v1/health/database")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "DATABASE_UNAVAILABLE"
    assert error["message"] == "数据库连接暂时不可用"
    assert error["request_id"] == response.headers["X-Request-ID"]


def test_not_found_returns_unified_error_response(client: TestClient) -> None:
    response = client.get("/api/v1/missing")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "HTTP_404"
    assert error["message"] == "请求的接口或资源不存在"
    assert error["request_id"] == response.headers["X-Request-ID"]
