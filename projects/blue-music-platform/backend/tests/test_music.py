from pathlib import Path
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.adapters.music_generation import MusicProviderError, SunoOfficialMusicProvider
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import create_app
from app.models import User, UserRole
from app.services.music_storage import StoredMusicObject
from app.services.music import get_music_task
from tests.fakes import FakeSunoProvider


class MusicContext(NamedTuple):
    client: TestClient
    token: str
    provider: FakeSunoProvider
    storage_root: Path


@pytest.fixture
def music_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> MusicContext:
    monkeypatch.setattr(settings, "AI_PROVIDER", "local")
    monkeypatch.setattr(settings, "AI_MODEL", "")
    monkeypatch.setattr(settings, "MUSIC_QUEUE_MODE", "inline")
    monkeypatch.setattr(settings, "SUNO_PROVIDER_IMPLEMENTATION", "official")
    storage_root = tmp_path / "music"
    monkeypatch.setattr(settings, "MUSIC_STORAGE_DIR", str(storage_root))
    provider = FakeSunoProvider()
    monkeypatch.setattr(
        "app.services.music.get_music_provider",
        lambda *_args, **_kwargs: provider,
    )

    def archive_audio(
        task_id: int,
        result_id: int,
        _url: str,
        _media_type: str,
    ) -> StoredMusicObject:
        relative = Path(str(task_id)) / f"{result_id}.mp3"
        target = storage_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"ID3-suno-test-audio")
        return StoredMusicObject(backend="local", key=relative.as_posix())

    monkeypatch.setattr("app.services.music._archive_audio", archive_audio)
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
        yield MusicContext(
            client=client,
            token=login.json()["access_token"],
            provider=provider,
            storage_root=storage_root,
        )
    test_app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _headers(context: MusicContext) -> dict[str, str]:
    return {"Authorization": f"Bearer {context.token}"}


def _lyrics_version_id(context: MusicContext, theme: str = "城市夜归人") -> int:
    response = context.client.post(
        "/api/v1/lyrics/tasks",
        headers=_headers(context),
        json={"theme": theme, "genre_tags": ["流行"], "mood_tags": ["治愈"]},
    )
    assert response.status_code == 201
    return response.json()["versions"][0]["id"]


def _create_music(context: MusicContext, title: str = "城市的灯") -> dict:
    response = context.client.post(
        "/api/v1/music/tasks",
        headers=_headers(context),
        json={
            "lyrics_version_id": _lyrics_version_id(context, title),
            "title": title,
            "style_prompt": "Mandopop, warm male vocal, piano and strings",
        },
    )
    assert response.status_code == 202
    detail = context.client.get(
        f"/api/v1/music/tasks/{response.json()['id']}",
        headers=_headers(context),
    )
    assert detail.status_code == 200
    return detail.json()


def test_music_generation_archives_audio_and_records_usage(
    music_context: MusicContext,
) -> None:
    task = _create_music(music_context)

    assert task["status"] == "completed"
    assert task["provider"] == "suno"
    assert task["model"] == "suno-test-model"
    assert len(task["results"]) == 1
    assert task["api_usage"][0]["provider"] == "suno"
    assert task["api_usage"][0]["usage_unit"] == "songs"
    assert task["api_usage"][0]["usage_quantity"] == 1
    assert music_context.provider.generated[0].lyrics

    result = task["results"][0]
    audio = music_context.client.get(
        f"/api/v1{result['audio_path']}",
        headers=_headers(music_context),
    )
    download = music_context.client.get(
        f"/api/v1{result['download_path']}",
        headers=_headers(music_context),
    )
    assert audio.status_code == 200
    assert audio.content == b"ID3-suno-test-audio"
    assert download.status_code == 200
    assert "attachment" in download.headers["content-disposition"]


def test_music_result_can_be_extended_and_deleted(
    music_context: MusicContext,
) -> None:
    original = _create_music(music_context, "第一段旅程")
    source = original["results"][0]
    extension = music_context.client.post(
        f"/api/v1/music/results/{source['id']}/extend",
        headers=_headers(music_context),
        json={"title": "第二段旅程", "requirements": "延长副歌"},
    )
    assert extension.status_code == 202
    detail = music_context.client.get(
        f"/api/v1/music/tasks/{extension.json()['id']}",
        headers=_headers(music_context),
    ).json()

    assert detail["status"] == "completed"
    assert detail["operation"] == "extend"
    assert detail["source_result_id"] == source["id"]
    assert music_context.provider.extended[0].source_external_id == source["external_id"]

    deleted = music_context.client.delete(
        f"/api/v1/music/results/{detail['results'][0]['id']}",
        headers=_headers(music_context),
    )
    assert deleted.status_code == 204
    results = music_context.client.get(
        "/api/v1/music/results",
        headers=_headers(music_context),
    ).json()
    assert results["total"] == 1


def test_music_tasks_support_deduplicated_bulk_delete(
    music_context: MusicContext,
) -> None:
    first = _create_music(music_context, "待删除一")
    second = _create_music(music_context, "待删除二")
    deleted = music_context.client.request(
        "DELETE",
        "/api/v1/music/tasks",
        headers=_headers(music_context),
        json={"task_ids": [first["id"], first["id"], second["id"]]},
    )

    assert deleted.status_code == 200
    assert deleted.json() == {
        "deleted_count": 2,
        "deleted_task_ids": [first["id"], second["id"]],
    }
    history = music_context.client.get(
        "/api/v1/music/tasks",
        headers=_headers(music_context),
    ).json()
    assert history["total"] == 0
    assert not music_context.storage_root.exists() or not any(
        music_context.storage_root.rglob("*.mp3")
    )


def test_unconfigured_official_suno_fails_with_actionable_error(
    music_context: MusicContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SUNO_API_BASE_URL", "")
    monkeypatch.setattr(settings, "SUNO_API_KEY", "")
    monkeypatch.setattr(
        "app.services.music.get_music_provider",
        lambda *_args, **_kwargs: SunoOfficialMusicProvider(),
    )
    response = music_context.client.post(
        "/api/v1/music/tasks",
        headers=_headers(music_context),
        json={"lyrics_version_id": _lyrics_version_id(music_context)},
    )
    task = music_context.client.get(
        f"/api/v1/music/tasks/{response.json()['id']}",
        headers=_headers(music_context),
    ).json()

    assert task["status"] == "failed"
    assert task["error_code"] == "SUNO_API_NOT_CONFIGURED"
    assert "Suno Platform" in task["error_message"]


def test_running_music_task_cannot_be_deleted(
    music_context: MusicContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.v1.routes.music.dispatch_music_task",
        lambda db, task_id: get_music_task(db, task_id),
    )
    response = music_context.client.post(
        "/api/v1/music/tasks",
        headers=_headers(music_context),
        json={"lyrics_version_id": _lyrics_version_id(music_context)},
    )
    deleted = music_context.client.delete(
        f"/api/v1/music/tasks/{response.json()['id']}",
        headers=_headers(music_context),
    )

    assert deleted.status_code == 409
    assert deleted.json()["error"]["code"] == "MUSIC_TASK_DELETE_CONFLICT"


def test_retryable_music_error_uses_persisted_attempts(
    music_context: MusicContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_generate = music_context.provider.generate
    attempts = 0

    def flaky_generate(payload):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise MusicProviderError(
                "temporary upstream failure",
                code="SUNO_COMPAT_UPSTREAM_ERROR",
                retryable=True,
            )
        return original_generate(payload)

    monkeypatch.setattr(settings, "MUSIC_RETRY_BASE_SECONDS", 0)
    monkeypatch.setattr(settings, "MUSIC_RETRY_MAX_SECONDS", 0)
    monkeypatch.setattr(music_context.provider, "generate", flaky_generate)

    task = _create_music(music_context, "自动重试")

    assert task["status"] == "completed"
    assert task["attempt_count"] == 2
    assert task["next_attempt_at"] is None


def test_hcaptcha_requires_human_and_supports_manual_requeue(
    music_context: MusicContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def require_human(_payload):
        raise MusicProviderError(
            "human verification required",
            code="SUNO_HUMAN_VERIFICATION_REQUIRED",
            requires_human=True,
        )

    monkeypatch.setattr(music_context.provider, "generate", require_human)
    task = _create_music(music_context, "人工验证")

    assert task["status"] == "failed"
    assert task["provider_status"] == "waiting_human_verification"
    retried = music_context.client.post(
        f"/api/v1/music/tasks/{task['id']}/retry",
        headers=_headers(music_context),
    )
    assert retried.status_code == 200
    assert retried.json()["status"] == "failed"
    assert retried.json()["attempt_count"] == 2


def test_provider_status_exposes_queue_and_persisted_quota(
    music_context: MusicContext,
) -> None:
    _create_music(music_context, "额度快照")
    response = music_context.client.get(
        "/api/v1/music/provider-status",
        headers=_headers(music_context),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["implementation"] == "official"
    assert body["queue_mode"] == "inline"
    assert body["quota"]["status"] == "available"
    assert body["quota"]["credits_remaining"] == 80
