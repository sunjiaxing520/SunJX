import httpx
import pytest

from app.adapters.music_generation import (
    MusicGenerationInput,
    MusicProviderError,
    SunoCompatibilityMusicProvider,
)
from app.core.config import settings


@pytest.fixture
def compat_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SUNO_COMPAT_ENABLED", True)
    monkeypatch.setattr(settings, "SUNO_COMPAT_ALLOW_REMOTE", False)
    monkeypatch.setattr(settings, "SUNO_REQUEST_TIMEOUT_SECONDS", 5)
    monkeypatch.setattr(settings, "SUNO_GENERATION_TIMEOUT_SECONDS", 5)


def _payload() -> MusicGenerationInput:
    return MusicGenerationInput(
        title="城市的灯",
        lyrics="[Verse]\n夜色落在肩上",
        style_prompt="Mandopop, warm male vocal",
        instrumental=False,
        negative_tags=["harsh vocal"],
        requirements="piano and strings",
    )


def test_compatibility_provider_normalizes_generation_and_quota(
    compat_settings: None,
) -> None:
    seen_headers: list[httpx.Headers] = []
    submitted_ids: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(request.headers)
        if request.url.path == "/api/custom_generate":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "track-1",
                        "title": "城市的灯",
                        "audio_url": "https://cdn.example.com/track-1.mp3",
                        "image_url": "https://cdn.example.com/track-1.jpg",
                        "duration": 95.4,
                        "status": "streaming",
                    }
                ],
            )
        if request.url.path == "/api/get_limit":
            return httpx.Response(
                200,
                json={
                    "credits_left": 80,
                    "monthly_usage": 20,
                    "monthly_limit": 100,
                    "period": "month",
                },
            )
        return httpx.Response(404, json={"error": "not found"})

    provider = SunoCompatibilityMusicProvider(
        base_url="http://localhost:3000",
        shared_token="internal-test-token",
        model="chirp-test",
        on_submitted=submitted_ids.append,
        transport=httpx.MockTransport(handler),
    )

    output = provider.generate(_payload())
    quota = provider.get_quota()

    assert output.external_task_id == "track-1"
    assert submitted_ids == ["track-1"]
    assert output.tracks[0].duration_seconds == 95
    assert output.call.usage_unit == "songs"
    assert quota.credits_remaining == 80
    assert quota.limit == 100
    assert all("cookie" not in headers for headers in seen_headers)
    assert all(
        headers["authorization"] == "Bearer internal-test-token"
        for headers in seen_headers
    )


def test_compatibility_provider_requires_human_for_hcaptcha(
    compat_settings: None,
) -> None:
    provider = SunoCompatibilityMusicProvider(
        base_url="http://localhost:3000",
        shared_token="internal-test-token",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                409,
                json={"error": "hCaptcha challenge required"},
            )
        ),
    )

    with pytest.raises(MusicProviderError) as captured:
        provider.generate(_payload())

    assert captured.value.code == "SUNO_HUMAN_VERIFICATION_REQUIRED"
    assert captured.value.requires_human is True
    assert captured.value.retryable is False


def test_compatibility_provider_detects_hcaptcha_in_failed_track(
    compat_settings: None,
) -> None:
    provider = SunoCompatibilityMusicProvider(
        base_url="http://localhost:3000",
        shared_token="internal-test-token",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json=[
                    {
                        "id": "track-1",
                        "status": "failed",
                        "error_message": "hCaptcha challenge required",
                    }
                ],
            )
        ),
    )

    with pytest.raises(MusicProviderError) as captured:
        provider.generate(_payload())

    assert captured.value.code == "SUNO_HUMAN_VERIFICATION_REQUIRED"
    assert captured.value.requires_human is True


def test_compatibility_provider_fails_when_any_track_fails(
    compat_settings: None,
) -> None:
    provider = SunoCompatibilityMusicProvider(
        base_url="http://localhost:3000",
        shared_token="internal-test-token",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json=[
                    {
                        "id": "track-1",
                        "status": "streaming",
                        "audio_url": "https://cdn.example.com/track-1.mp3",
                    },
                    {
                        "id": "track-2",
                        "status": "failed",
                        "error_message": "generation failed",
                    },
                ],
            )
        ),
    )

    with pytest.raises(MusicProviderError) as captured:
        provider.generate(_payload())

    assert captured.value.code == "SUNO_GENERATION_FAILED"
    assert captured.value.retryable is False


def test_compatibility_provider_normalizes_rate_limit(
    compat_settings: None,
) -> None:
    provider = SunoCompatibilityMusicProvider(
        base_url="http://localhost:3000",
        shared_token="internal-test-token",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                429,
                headers={"Retry-After": "45"},
                json={"error": "too many requests"},
            )
        ),
    )

    with pytest.raises(MusicProviderError) as captured:
        provider.generate(_payload())

    assert captured.value.code == "SUNO_RATE_LIMITED"
    assert captured.value.retryable is True
    assert captured.value.retry_after_seconds == 45


def test_compatibility_provider_rejects_plain_http_remote_service(
    compat_settings: None,
) -> None:
    with pytest.raises(MusicProviderError) as captured:
        SunoCompatibilityMusicProvider(
            base_url="http://example.com",
            shared_token="internal-test-token",
        )

    assert captured.value.code == "SUNO_COMPAT_REMOTE_FORBIDDEN"
