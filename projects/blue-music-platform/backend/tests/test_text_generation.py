import json

import httpx
import pytest

from app.adapters import text_generation
from app.adapters.text_generation import (
    GeneratedDirection,
    GeneratedLyrics,
    LocalTextProvider,
    OpenAICompatibleTextProvider,
    TextProviderConfig,
    TextProviderError,
)
from app.core.config import settings
from app.schemas.analysis import CreationDirection


def _lyrics_sections() -> list[dict[str, str]]:
    verse1 = "迎着清晨奔向远方\n把新的故事写在路旁"
    verse2 = "穿过风雨依然晴朗\n每一步都有坚定方向"
    chorus1 = "抬头看见同一道光\n让心里的愿望自由生长"
    chorus2 = "换一句会被统一首句\n让我们的歌继续回响"
    return [
        {"name": "Verse 1", "content": verse1},
        {"name": "Verse 2", "content": verse2},
        {"name": "Chorus1", "content": chorus1},
        {"name": "Chorus2", "content": chorus2},
        {"name": "Interlude", "content": "纯音乐"},
        {"name": "Verse 2", "content": "这段会被统一"},
        {"name": "Chorus1", "content": "这段会被统一"},
        {"name": "Chorus2", "content": "这段会被统一"},
        {"name": "Chorus1", "content": "这段会被统一"},
        {"name": "Chorus2", "content": "这段会被统一"},
        {"name": "Outro", "content": "不应保留"},
    ]


def _memory_insight_payload() -> dict[str, object]:
    return {
        "requirement_summary": "围绕成长主题创作一首完整中文歌曲。",
        "strategy_summary": "用通勤场景推进主歌叙事，在副歌集中强化向前的力量。",
        "result_summary": "形成主题明确、结构完整且副歌记忆点清晰的歌词版本。",
        "reusable_patterns": [
            "主歌使用连续场景推进叙事。",
            "副歌用简短首句集中表达主题。",
        ],
        "highlight_summary": "把日常通勤意象转化为持续向前的情绪线索。",
    }


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
                                "sections": _lyrics_sections(),
                                "memory_insight": _memory_insight_payload(),
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
    system_prompt = captured_request["messages"][0]["content"]
    assert "资深中文词曲作者" in system_prompt
    assert "Verse 1、Verse 2、Chorus1、Chorus2、Interlude" in system_prompt
    assert "Interlude 和 Outro 的 content 必须是空字符串" in system_prompt
    assert "所有有歌词的句子必须统一押同一个韵脚" in system_prompt
    assert "歌词创作提炼 Skill" in system_prompt
    assert "用户主动确认的结果" in system_prompt
    assert "真实榜单歌词证据" in system_prompt
    assert "不得照抄用户原话或歌词正文" in system_prompt
    assert result.output.memory_insight.result_summary.startswith("形成主题明确")

    captured_request.clear()
    monkeypatch.setattr(settings, "AI_BASE_URL", "https://api.example.com/v1")
    OpenAICompatibleTextProvider().generate_lyrics({"theme": "测试"}, variation=2)
    assert "thinking" not in captured_request


@pytest.mark.parametrize("mode", ["analysis", "prompt"])
def test_composition_provider_keeps_fixed_contract_and_returns_features(monkeypatch, mode):
    captured = {}

    class CompositionResponse(FakeResponse):
        def json(self):
            body = super().json()
            content = json.loads(body["choices"][0]["message"]["content"])
            content["creation_features"] = {
                "theme": "重逢", "language": "中文", "genre_tags": ["民谣"],
                "mood_tags": ["温暖"], "scene_tags": ["夜晚"], "keywords": ["晚风"],
                "tempo": "slow", "vocal_gender": "male", "vocal_style": "自然叙事",
            }
            body["choices"][0]["message"]["content"] = json.dumps(content)
            return body

    def fake_post(*args, **kwargs):
        captured.update(kwargs["json"])
        return CompositionResponse()

    monkeypatch.setattr(settings, "AI_API_KEY", "test-key")
    monkeypatch.setattr(text_generation.httpx, "post", fake_post)
    composition = {"mode": mode, "prompt": "写一首关于重逢的歌曲", "analysis_direction": _direction_payload() if mode == "analysis" else None}
    result = OpenAICompatibleTextProvider().generate_lyrics({"composition": composition}, 1)
    assert result.output.creation_features.genre_tags == ["民谣"]
    assert result.call.total_tokens == 200
    system = captured["messages"][0]["content"]
    assert "资深中文词曲作者" in system
    assert "所有有歌词的句子必须统一押同一个韵脚" in system
    assert "Interlude 和 Outro 的 content 必须是空字符串" in system
    assert "creation_features" in system
    assert "composition.prompt" in system
    assert len(result.output.sections) == 11
    assert result.output.sections[4].content == result.output.sections[10].content == ""
    assert result.output.sections[2].content.splitlines()[0] == result.output.sections[3].content.splitlines()[0]


def test_lyrics_memory_editor_returns_confirmable_operations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_request: dict[str, object] = {}

    class MemoryResponse(FakeResponse):
        def json(self) -> dict[str, object]:
            body = super().json()
            body["choices"] = [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "reply": "建议新增一条副歌规则。",
                                "operations": [
                                    {
                                        "action": "add_rule",
                                        "event_id": None,
                                        "title": "副歌长度",
                                        "content": "副歌核心句保持简短。",
                                        "reason": "管理员明确要求",
                                    }
                                ],
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
            return body

    def fake_post(*args, **kwargs):
        captured_request.update(kwargs.get("json") or {})
        return MemoryResponse()

    monkeypatch.setattr(text_generation.httpx, "post", fake_post)
    provider = OpenAICompatibleTextProvider(
        TextProviderConfig(
            template_key="kimi",
            protocol="openai_compatible",
            base_url="https://api.moonshot.cn/v1",
            api_key="test-key",
            model="kimi-k3",
            max_tokens_parameter="max_completion_tokens",
            max_retries=1,
        )
    )

    result = provider.edit_lyrics_memory(
        {
            "instruction": "副歌短一点",
            "current_memory": {},
            "event_catalog": [],
        }
    )

    assert result.output.operations[0].action == "add_rule"
    assert result.output.operations[0].title == "副歌长度"
    system_prompt = captured_request["messages"][0]["content"]
    assert "等待管理员再次确认" in system_prompt
    assert "不得删除数据库记录" in system_prompt


def test_lyrics_memory_distillation_returns_abstract_insight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_request: dict[str, object] = {}

    class DistillationResponse(FakeResponse):
        def json(self) -> dict[str, object]:
            body = super().json()
            body["choices"] = [{
                "message": {
                    "content": json.dumps(_memory_insight_payload(), ensure_ascii=False)
                }
            }]
            return body

    def fake_post(*args, **kwargs):
        captured_request.update(kwargs.get("json") or {})
        return DistillationResponse()

    monkeypatch.setattr(text_generation.httpx, "post", fake_post)
    provider = OpenAICompatibleTextProvider(
        TextProviderConfig(
            template_key="kimi",
            protocol="openai_compatible",
            base_url="https://api.moonshot.cn/v1",
            api_key="test-key",
            model="kimi-k2.5",
            max_retries=1,
        )
    )

    result = provider.distill_lyrics_memory(
        {
            "title": "测试歌名",
            "user_request_evidence": "副歌更有力量",
            "accepted_lyrics": "这是不应该被照抄的歌词",
        }
    )

    assert result.output.result_summary.startswith("形成主题明确")
    system_prompt = captured_request["messages"][0]["content"]
    assert "不得照抄用户原话" in system_prompt
    assert "不得引用或复述歌词原文" in system_prompt


def test_local_revision_memory_does_not_copy_the_instruction() -> None:
    instruction = "副歌更有力量"
    result = LocalTextProvider().revise_lyrics(
        {
            "instruction": instruction,
            "original": {"title": "向光而行"},
            "task": {"theme": "成长"},
        }
    )

    assert instruction not in result.output.memory_insight.requirement_summary


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


def test_kimi_k3_uses_supported_request_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_request: dict[str, object] = {}

    def fake_post(*args, **kwargs):
        captured_request.update(kwargs.get("json") or {})
        return FakeResponse()

    monkeypatch.setattr(text_generation.httpx, "post", fake_post)
    provider = OpenAICompatibleTextProvider(
        TextProviderConfig(
            template_key="kimi",
            protocol="openai_compatible",
            base_url="https://api.moonshot.cn/v1",
            api_key="test-key",
            model="kimi-k3",
            supports_json_mode=True,
            max_tokens_parameter="max_completion_tokens",
            max_retries=1,
        )
    )

    provider.generate_lyrics({"theme": "测试"}, variation=1)

    assert captured_request["max_completion_tokens"] == 3500
    assert captured_request["response_format"] == {"type": "json_object"}
    assert captured_request["reasoning_effort"] == "low"
    assert "temperature" not in captured_request

    captured_request.clear()
    provider.test_connection()
    assert captured_request["max_completion_tokens"] == 256


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
        sections = _lyrics_sections()
        sections[0].pop("content")
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
                                    "sections": sections,
                                    "memory_insight": _memory_insight_payload(),
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


def test_generated_lyrics_enforces_client_structure() -> None:
    generated = GeneratedLyrics.model_validate(
        {
            "title": "向光而行",
            "style_prompt": "励志流行",
            "sections": _lyrics_sections(),
            "memory_insight": _memory_insight_payload(),
        }
    )

    assert [section.name for section in generated.sections] == [
        "Verse 1",
        "Verse 2",
        "Chorus1",
        "Chorus2",
        "Interlude",
        "Verse 2",
        "Chorus1",
        "Chorus2",
        "Chorus1",
        "Chorus2",
        "Outro",
    ]
    assert generated.sections[4].content == ""
    assert generated.sections[-1].content == ""
    assert generated.sections[1].content == generated.sections[5].content
    assert generated.sections[2].content == generated.sections[6].content
    assert generated.sections[2].content.splitlines()[0] == (
        generated.sections[3].content.splitlines()[0]
    )
