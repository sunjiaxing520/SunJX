from fastapi.testclient import TestClient


def test_root_returns_running_message(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
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
