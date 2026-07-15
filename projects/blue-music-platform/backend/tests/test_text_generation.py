import json

import httpx
import pytest

from app.adapters import text_generation
from app.adapters.text_generation import (
    GeneratedDirection,
    OpenAICompatibleTextProvider,
    TextProviderConfig,
    TextProviderError,
)
from app.core.config import settings
from app.schemas.analysis import CreationDirection


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {
            "id": "request-usage-123",
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "title": "测试歌名",
                                "style_prompt": "流行, 温柔",
                                "sections": [
                                    {"name": "Verse", "content": "第一段"},
                                    {"name": "Chorus", "content": "副歌"},
                                    {"name": "Outro", "content": "尾声"},
                                ],
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 80,
                "total_tokens": 200,
                "prompt_tokens_details": {"cached_tokens": 20},
            },
        }


def _direction_payload() -> dict[str, object]:
    return {
        "name": "夏日方向",
        "language": "中文",
        "genre_tags": ["流行"],
        "mood_tags": ["轻松"],
        "theme_keywords": ["夏天"],
        "scene_tags": ["海边"],
        "tempo": "medium-fast",
        "vocal_gender": "不限",
        "vocal_style": "自然",
        "instrument_tags": ["吉他"],
        "structure": ["Verse", "Chorus", "Outro"],
        "hook_direction": "副歌抓耳",
        "negative_constraints": [],
    }


def test_analysis_direction_normalizes_provider_aliases() -> None:
    generated = GeneratedDirection.model_validate(_direction_payload())
    response = CreationDirection.model_validate(_direction_payload())

    assert generated.tempo == "fast"
    assert response.tempo == "fast"
    assert generated.vocal_gender == "unspecified"
    assert response.vocal_gender == "unspecified"


def test_openai_compatible_provider_returns_usage_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_request: dict[str, object] = {}

    def fake_post(*args, **kwargs):
        captured_request.update(kwargs.get("json") or {})
        return FakeResponse()

    monkeypatch.setattr(settings, "AI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    monkeypatch.setattr(settings, "AI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "AI_MODEL", "glm-4.7-flash")
    monkeypatch.setattr(settings, "AI_MAX_RETRIES", 1)
    monkeypatch.setattr(text_generation.httpx, "post", fake_post)

    result = OpenAICompatibleTextProvider().generate_lyrics(
        {"theme": "测试"},
        variation=1,
    )

    assert result.output.title == "测试歌名"
    assert result.call.endpoint.endswith("/chat/completions")
    assert result.call.request_id == "request-usage-123"
    assert result.call.input_tokens == 120
    assert result.call.output_tokens == 80
    assert result.call.cached_tokens == 20
    assert result.call.total_tokens == 200
    assert result.call.usage_quantity == 200
    assert captured_request["max_tokens"] == settings.AI_LYRICS_MAX_OUTPUT_TOKENS
    assert captured_request["thinking"] == {"type": "disabled"}

    captured_request.clear()
    monkeypatch.setattr(settings, "AI_BASE_URL", "https://api.example.com/v1")
    OpenAICompatibleTextProvider().generate_lyrics({"theme": "测试"}, variation=2)
    assert "thinking" not in captured_request


def test_provider_config_controls_json_and_token_parameter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_request: dict[str, object] = {}

    def fake_post(*args, **kwargs):
        captured_request.update(kwargs.get("json") or {})
        return FakeResponse()

    monkeypatch.setattr(text_generation.httpx, "post", fake_post)
    provider = OpenAICompatibleTextProvider(
        TextProviderConfig(
            template_key="minimax",
            protocol="openai_compatible",
            base_url="https://api.minimaxi.com/v1",
            api_key="test-key",
            model="MiniMax-M2.7",
            supports_json_mode=False,
            max_tokens_parameter="max_completion_tokens",
            max_retries=1,
        )
    )

    provider.generate_lyrics({"theme": "测试"}, variation=1)

    assert captured_request["max_completion_tokens"] == 3500
    assert "max_tokens" not in captured_request
    assert "response_format" not in captured_request


def test_provider_read_timeout_does_not_duplicate_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_post(url, **kwargs):
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("timed out", request=httpx.Request("POST", url))

    monkeypatch.setattr(text_generation.httpx, "post", fake_post)
    monkeypatch.setattr(text_generation.time, "sleep", lambda _: None)
    provider = OpenAICompatibleTextProvider(
        TextProviderConfig(
            template_key="bigmodel",
            protocol="openai_compatible",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            api_key="test-key",
            model="glm-4.7-flash",
            request_timeout_seconds=12,
            max_retries=2,
        )
    )

    with pytest.raises(TextProviderError) as error:
        provider.test_connection()

    assert str(error.value) == "AI 接口请求超时（单次等待上限 12 秒）"
    assert error.value.call is not None
    assert error.value.call.attempt_count == 1
    assert calls == 1


def test_provider_rate_limit_without_retry_after_stops_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_post(url, **kwargs):
        nonlocal calls
        calls += 1
        return httpx.Response(
            429,
            headers={"x-request-id": "provider-rate-limit-123"},
            json={"error": {"code": "1302", "message": "并发数已达上限"}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(text_generation.httpx, "post", fake_post)
    monkeypatch.setattr(text_generation.time, "sleep", lambda _: None)
    provider = OpenAICompatibleTextProvider(
        TextProviderConfig(
            template_key="bigmodel",
            protocol="openai_compatible",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            api_key="test-key",
            model="glm-4.7-flash",
            max_retries=2,
        )
    )

    with pytest.raises(TextProviderError) as error:
        provider.test_connection()

    assert str(error.value) == "AI 接口返回 HTTP 429（1302：并发数已达上限）"
    assert error.value.call is not None
    assert error.value.call.attempt_count == 1
    assert error.value.call.request_id == "provider-rate-limit-123"
    assert calls == 1


def test_provider_rate_limit_respects_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    delays: list[float] = []

    def fake_post(url, **kwargs):
        nonlocal calls
        calls += 1
        request = httpx.Request("POST", url)
        if calls == 1:
            return httpx.Response(
                429,
                headers={"retry-after": "3"},
                json={"error": {"code": "1302", "message": "请稍后重试"}},
                request=request,
            )
        return httpx.Response(
            200,
            json={
                "id": "provider-recovered-123",
                "choices": [{"message": {"content": '{"status":"ok"}'}}],
            },
            request=request,
        )

    monkeypatch.setattr(text_generation.httpx, "post", fake_post)
    monkeypatch.setattr(text_generation.time, "sleep", delays.append)
    provider = OpenAICompatibleTextProvider(
        TextProviderConfig(
            template_key="bigmodel",
            protocol="openai_compatible",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            api_key="test-key",
            model="glm-4.7-flash",
            max_retries=2,
        )
    )

    result = provider.test_connection()

    assert result.output == {"status": "ok"}
    assert result.call.attempt_count == 2
    assert calls == 2
    assert delays == [3.0]


def test_provider_non_retryable_error_stops_and_redacts_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_post(url, **kwargs):
        nonlocal calls
        calls += 1
        return httpx.Response(
            401,
            json={
                "error": {
                    "code": "1001",
                    "message": "Authorization: secret-provider-token",
                }
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(text_generation.httpx, "post", fake_post)
    provider = OpenAICompatibleTextProvider(
        TextProviderConfig(
            template_key="bigmodel",
            protocol="openai_compatible",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            api_key="test-key",
            model="glm-4.7-flash",
            max_retries=2,
        )
    )

    with pytest.raises(TextProviderError) as error:
        provider.test_connection()

    assert "HTTP 401" in str(error.value)
    assert "secret-provider-token" not in str(error.value)
    assert error.value.call is not None
    assert error.value.call.attempt_count == 1
    assert calls == 1


def test_provider_empty_choices_returns_a_diagnostic_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(url, **kwargs):
        return httpx.Response(
            200,
            json={"id": "provider-empty-123", "choices": []},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(text_generation.httpx, "post", fake_post)
    provider = OpenAICompatibleTextProvider(
        TextProviderConfig(
            template_key="bigmodel",
            protocol="openai_compatible",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            api_key="test-key",
            model="glm-4.7-flash",
            max_retries=1,
        )
    )

    with pytest.raises(TextProviderError) as error:
        provider.test_connection()

    assert str(error.value) == "AI 接口响应中没有可用的生成结果"
    assert error.value.call is not None
    assert error.value.call.request_id == "provider-empty-123"


def test_lyrics_sections_require_name_and_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(url, **kwargs):
        return httpx.Response(
            200,
            json={
                "id": "provider-invalid-lyrics-123",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "title": "缺少字段",
                                    "style_prompt": "流行",
                                    "sections": [
                                        {"name": "Verse"},
                                        {"name": "Chorus", "content": "副歌"},
                                        {"name": "Outro", "content": "尾声"},
                                    ],
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ],
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(text_generation.httpx, "post", fake_post)
    provider = OpenAICompatibleTextProvider(
        TextProviderConfig(
            template_key="bigmodel",
            protocol="openai_compatible",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            api_key="test-key",
            model="glm-4.7-flash",
            max_retries=1,
        )
    )

    with pytest.raises(TextProviderError) as error:
        provider.generate_lyrics({"theme": "测试"}, variation=1)

    assert str(error.value) == (
        "AI 歌词结果字段不完整或类型不正确：sections.0.content (missing)"
    )
    assert error.value.call is not None
    assert error.value.call.request_id == "provider-invalid-lyrics-123"
