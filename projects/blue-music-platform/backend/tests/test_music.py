from pathlib import Path
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.adapters.music_generation import (
    MusicProviderError,
    SunoCompatibilityMusicProvider,
    SunoOfficialMusicProvider,
)
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


def test_member_music_quota_covers_generation_and_extension(
    music_context: MusicContext,
) -> None:
    member = music_context.client.post(
        "/api/v1/users",
        headers=_headers(music_context),
        json={
            "username": "music.member",
            "password": "member-password",
            "music_quota_remaining": 2,
        },
    )
    assert member.status_code == 201
    member_id = member.json()["id"]
    permissions = music_context.client.put(
        f"/api/v1/users/{member_id}/agent-permissions",
        headers=_headers(music_context),
        json={"agents": ["music"]},
    )
    assert permissions.status_code == 200
    login = music_context.client.post(
        "/api/v1/auth/login",
        json={"username": "music.member", "password": "member-password"},
    )
    member_headers = {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }
    lyrics_version_id = _lyrics_version_id(music_context, "额度测试")
    payload = {
        "lyrics_version_id": lyrics_version_id,
        "title": "额度测试",
        "style_prompt": "Mandopop",
    }

    generated = music_context.client.post(
        "/api/v1/music/tasks",
        headers=member_headers,
        json=payload,
    )
    assert generated.status_code == 202
    source_result_id = generated.json()["results"][0]["id"]
    extended = music_context.client.post(
        f"/api/v1/music/results/{source_result_id}/extend",
        headers=member_headers,
        json={"title": "额度测试续写"},
    )
    exhausted = music_context.client.post(
        "/api/v1/music/tasks",
        headers=member_headers,
        json=payload,
    )
    profile = music_context.client.get(
        "/api/v1/auth/me",
        headers=member_headers,
    )

    assert extended.status_code == 202
    assert exhausted.status_code == 403
    assert exhausted.json()["error"]["code"] == "MUSIC_TASK_QUOTA_EXHAUSTED"
    assert profile.json()["music_quota"] == {
        "is_unlimited": False,
        "remaining_tasks": 0,
        "used_tasks": 2,
    }


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
        f"/api/v1/music/tasks/{task['id']}/human-verification-complete",
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


def test_provider_status_waits_for_compatibility_session(
    music_context: MusicContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SUNO_PROVIDER_IMPLEMENTATION", "compatibility")
    monkeypatch.setattr(settings, "SUNO_COMPAT_ENABLED", True)
    monkeypatch.setattr(settings, "SUNO_COMPAT_BASE_URL", "http://localhost:3000")
    monkeypatch.setattr(settings, "SUNO_COMPAT_SHARED_TOKEN", "internal-test-token")
    monkeypatch.setattr(
        SunoCompatibilityMusicProvider,
        "get_runtime_status",
        lambda _provider: {
            "status": "waiting_cookie",
            "captcha_mode": "human_verification",
            "cookie_configured": False,
            "routes": ["GET /api/health", "POST /api/generate"],
        },
    )

    response = music_context.client.get(
        "/api/v1/music/provider-status",
        headers=_headers(music_context),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["implementation"] == "compatibility"
    assert body["configured"] is True
    assert body["integration_status"] == "waiting_session"
    assert body["runtime_status"] == "waiting_cookie"
    assert body["captcha_mode"] == "human_verification"
    assert body["cookie_configured"] is False
    assert "POST /api/generate" in body["compat_routes"]


def test_lyrics_assistant_and_review_agent_respect_member_memory_privacy(
    music_context: MusicContext,
) -> None:
    lyrics = music_context.client.post(
        "/api/v1/lyrics/tasks",
        headers=_headers(music_context),
        json={"theme": "Assistant review test", "genre_tags": ["pop"]},
    )
    assert lyrics.status_code == 201
    source_version = lyrics.json()["versions"][0]

    preview = music_context.client.post(
        f"/api/v1/lyrics/versions/{source_version['id']}/assistant",
        headers=_headers(music_context),
        json={"instruction": "Make the chorus more memorable."},
    )
    assert preview.status_code == 200
    assert preview.json()["role"] == "assistant"
    assert preview.json()["preview"]["content"]

    history = music_context.client.get(
        f"/api/v1/lyrics/versions/{source_version['id']}/assistant",
        headers=_headers(music_context),
    )
    assert [item["role"] for item in history.json()["items"]] == ["user", "assistant"]

    confirmed = music_context.client.post(
        f"/api/v1/lyrics/assistant-previews/{preview.json()['id']}/confirm",
        headers=_headers(music_context),
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["version_number"] == 2
    assert confirmed.json()["is_saved"] is True

    review_agent = music_context.client.post(
        "/api/v1/review-agents",
        headers=_headers(music_context),
        json={
            "name": "Lyrics quality review",
            "initialization_messages": [
                {
                    "role": "user",
                    "content": "Review lyrics with emphasis on rhythm, narrative, and chorus recall.",
                }
            ],
        },
    )
    assert review_agent.status_code == 201
    assert review_agent.json()["memory_detail"]

    member = music_context.client.post(
        "/api/v1/users",
        headers=_headers(music_context),
        json={
            "username": "review.member",
            "password": "member-password",
            "music_quota_remaining": 0,
        },
    )
    assert member.status_code == 201
    assignment = music_context.client.put(
        f"/api/v1/review-agents/{review_agent.json()['id']}/members",
        headers=_headers(music_context),
        json={"user_ids": [member.json()["id"]]},
    )
    assert assignment.status_code == 200

    member_login = music_context.client.post(
        "/api/v1/auth/login",
        json={"username": "review.member", "password": "member-password"},
    )
    member_headers = {"Authorization": f"Bearer {member_login.json()['access_token']}"}
    member_agents = music_context.client.get(
        "/api/v1/review-agents",
        headers=member_headers,
    )
    assert member_agents.status_code == 200
    assert member_agents.json()[0]["memory_summary"]
    assert member_agents.json()[0]["memory_detail"] is None
    assert member_agents.json()[0]["initialization_notes"] is None

    lyrics_options = music_context.client.get(
        "/api/v1/review-agents/lyrics-options",
        headers=member_headers,
    )
    assert lyrics_options.status_code == 200
    selected_option = next(
        item for item in lyrics_options.json() if item["id"] == confirmed.json()["id"]
    )
    assert selected_option["content"] == confirmed.json()["content"]
    assert selected_option["style_prompt"] == confirmed.json()["style_prompt"]
    assert selected_option["theme"] == "Assistant review test"
    assert selected_option["is_saved"] is True

    review = music_context.client.post(
        f"/api/v1/review-agents/{review_agent.json()['id']}/reviews",
        headers=member_headers,
        json={
            "lyrics_version_id": confirmed.json()["id"],
            "instruction": "Focus on the chorus.",
        },
    )
    assert review.status_code == 200
    assert review.json()["result"]["overall_score"] >= 0
    assert review.json()["result"]["dimensions"]

    unrelated_preview = music_context.client.post(
        f"/api/v1/review-agents/{review_agent.json()['id']}"
        f"/reviews/{review.json()['id']}/assistant-previews/{preview.json()['id']}/confirm",
        headers=member_headers,
    )
    assert unrelated_preview.status_code == 404
    assert unrelated_preview.json()["error"]["code"] == "REVIEW_REVISION_PREVIEW_NOT_FOUND"

    review_revision = music_context.client.post(
        f"/api/v1/review-agents/{review_agent.json()['id']}"
        f"/reviews/{review.json()['id']}/assistant",
        headers=member_headers,
        json={"instruction": "Revise the chorus using the review deductions."},
    )
    assert review_revision.status_code == 200
    assert review_revision.json()["role"] == "assistant"
    assert review_revision.json()["preview"]["content"]

    review_revision_history = music_context.client.get(
        f"/api/v1/review-agents/{review_agent.json()['id']}"
        f"/reviews/{review.json()['id']}/assistant",
        headers=member_headers,
    )
    assert review_revision_history.status_code == 200
    assert [item["role"] for item in review_revision_history.json()["items"]] == [
        "user",
        "assistant",
    ]

    second_review = music_context.client.post(
        f"/api/v1/review-agents/{review_agent.json()['id']}/reviews",
        headers=member_headers,
        json={"lyrics_version_id": confirmed.json()["id"]},
    )
    assert second_review.status_code == 200
    second_review_history = music_context.client.get(
        f"/api/v1/review-agents/{review_agent.json()['id']}"
        f"/reviews/{second_review.json()['id']}/assistant",
        headers=member_headers,
    )
    assert second_review_history.status_code == 200
    assert second_review_history.json()["items"] == []
    cross_review_preview = music_context.client.post(
        f"/api/v1/review-agents/{review_agent.json()['id']}"
        f"/reviews/{second_review.json()['id']}"
        f"/assistant-previews/{review_revision.json()['id']}/confirm",
        headers=member_headers,
    )
    assert cross_review_preview.status_code == 404
    assert cross_review_preview.json()["error"]["code"] == "REVIEW_REVISION_PREVIEW_NOT_FOUND"

    saved_revision = music_context.client.post(
        f"/api/v1/review-agents/{review_agent.json()['id']}"
        f"/reviews/{review.json()['id']}"
        f"/assistant-previews/{review_revision.json()['id']}/confirm",
        headers=member_headers,
    )
    assert saved_revision.status_code == 200
    assert saved_revision.json()["version_number"] == 3
    assert saved_revision.json()["is_saved"] is True
    assert saved_revision.json()["content"] == review_revision.json()["preview"]["content"]

    memory = music_context.client.post(
        f"/api/v1/review-agents/{review_agent.json()['id']}/memory",
        headers=member_headers,
        json={"content": "Prefer restrained verses before a stronger chorus."},
    )
    assert memory.status_code == 200
    assert memory.json()["summary"]
    assert memory.json()["detail"] is None

    admin_detail = music_context.client.get(
        f"/api/v1/review-agents/{review_agent.json()['id']}",
        headers=_headers(music_context),
    )
    assert admin_detail.status_code == 200
    assert admin_detail.json()["memory_detail"]
    assert admin_detail.json()["initialization_notes"]


def test_music_settings_tags_adaptation_regeneration_and_favorite(
    music_context: MusicContext,
) -> None:
    settings_before = music_context.client.get(
        "/api/v1/music/settings",
        headers=_headers(music_context),
    )
    assert settings_before.status_code == 200
    assert settings_before.json()["active_model"] == "v4.5"

    settings_updated = music_context.client.put(
        "/api/v1/music/settings",
        headers=_headers(music_context),
        json={"active_model": "v4.5"},
    )
    assert settings_updated.status_code == 200
    assert settings_updated.json()["updated_by_id"]

    submitted = music_context.client.post(
        "/api/v1/music/tasks",
        headers=_headers(music_context),
        json={
            "lyrics_version_id": _lyrics_version_id(music_context, "Tagged music"),
            "title": "Tagged music",
            "style_prompt": "Warm contemporary pop",
            "style_tags": ["pop", "r&b"],
            "negative_tags": ["metal"],
        },
    )
    assert submitted.status_code == 202
    source = music_context.client.get(
        f"/api/v1/music/tasks/{submitted.json()['id']}",
        headers=_headers(music_context),
    ).json()
    assert source["style_tags"] == ["pop", "r&b"]
    assert source["negative_tags"] == ["metal"]
    assert music_context.provider.generated[-1].style_tags == ["pop", "r&b"]

    favorite = music_context.client.post(
        "/api/v1/favorites",
        headers=_headers(music_context),
        json={"item_type": "music", "target_id": source["results"][0]["id"], "category": "S"},
    )
    assert favorite.status_code == 201
    assert favorite.json()["category"] == "S"
    moved = music_context.client.patch(
        f"/api/v1/favorites/{favorite.json()['id']}",
        headers=_headers(music_context),
        json={"category": "A", "note": "Keep for demo."},
    )
    assert moved.status_code == 200
    assert moved.json()["category"] == "A"
    filtered = music_context.client.get(
        "/api/v1/favorites",
        headers=_headers(music_context),
        params={"category": "A", "item_type": "music"},
    )
    assert filtered.json()["total"] == 1

    unauthorized_adaptation = music_context.client.post(
        f"/api/v1/music/results/{source['results'][0]['id']}/adapt",
        headers=_headers(music_context),
        json={"rights_confirmed": False},
    )
    assert unauthorized_adaptation.status_code == 422

    adaptation = music_context.client.post(
        f"/api/v1/music/results/{source['results'][0]['id']}/adapt",
        headers=_headers(music_context),
        json={
            "rights_confirmed": True,
            "rights_note": "Written authorization is on file.",
            "adaptation_mode": "extend",
            "style_tags": ["indie pop"],
            "negative_tags": ["metal"],
        },
    )
    assert adaptation.status_code == 202
    adapted = music_context.client.get(
        f"/api/v1/music/tasks/{adaptation.json()['id']}",
        headers=_headers(music_context),
    ).json()
    assert adapted["operation"] == "adapt"
    assert adapted["rights_confirmed"] is True
    assert adapted["adaptation_mode"] == "extend"
    assert adapted["style_tags"] == ["indie pop"]
    assert music_context.provider.extended[-1].source_external_id == source["results"][0]["external_id"]

    regenerated = music_context.client.post(
        f"/api/v1/music/tasks/{source['id']}/regenerate",
        headers=_headers(music_context),
    )
    assert regenerated.status_code == 202
    regenerated_task = music_context.client.get(
        f"/api/v1/music/tasks/{regenerated.json()['id']}",
        headers=_headers(music_context),
    ).json()
    assert regenerated_task["status"] == "completed"
    assert regenerated_task["style_tags"] == ["pop", "r&b"]
