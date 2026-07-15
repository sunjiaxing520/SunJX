import json

import pytest

from app.adapters import text_generation
from app.adapters.text_generation import (
    OpenAICompatibleTextProvider,
    TextProviderConfig,
)
from app.core.config import settings


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
