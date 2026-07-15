import json
import logging
import re
import time
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Generic, Protocol, TypeVar
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.core.logging import LOGGER_NAME, redact_sensitive_values
from app.core.time import utc_now


provider_logger = logging.getLogger(f"{LOGGER_NAME}.providers")


class TextProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        call: "ProviderCallMetadata | None" = None,
    ) -> None:
        super().__init__(message)
        self.call = call


@dataclass(frozen=True)
class ProviderCallMetadata:
    method: str
    endpoint: str
    is_external: bool
    request_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    usage_unit: str = "tokens"
    usage_quantity: float = 0
    attempt_count: int = 1
    duration_ms: int | None = None
    raw_usage: dict[str, Any] | None = None
    started_at: datetime = field(default_factory=utc_now)
    completed_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class TextProviderConfig:
    template_key: str
    protocol: str
    base_url: str
    api_key: str
    model: str
    supports_json_mode: bool = True
    max_tokens_parameter: str = "max_tokens"
    request_timeout_seconds: float = 180
    max_retries: int = 2
    analysis_max_output_tokens: int = 2500
    lyrics_max_output_tokens: int = 3500


OutputT = TypeVar("OutputT")


@dataclass(frozen=True)
class ProviderResult(Generic[OutputT]):
    output: OutputT
    call: ProviderCallMetadata


class GeneratedDirection(BaseModel):
    name: str
    language: str = "中文"
    genre_tags: list[str] = Field(min_length=1, max_length=8)
    mood_tags: list[str] = Field(min_length=1, max_length=8)
    theme_keywords: list[str] = Field(min_length=1, max_length=12)
    scene_tags: list[str] = Field(min_length=1, max_length=8)
    tempo: str
    vocal_gender: str
    vocal_style: str
    instrument_tags: list[str] = Field(min_length=1, max_length=10)
    structure: list[str] = Field(min_length=3, max_length=12)
    hook_direction: str
    negative_constraints: list[str] = Field(default_factory=list, max_length=10)


class GeneratedAnalysis(BaseModel):
    trend_summary: str
    creation_directions: list[GeneratedDirection] = Field(min_length=1, max_length=3)


class GeneratedLyricsSection(BaseModel):
    name: str = Field(min_length=1)
    content: str = Field(min_length=1)


class GeneratedLyrics(BaseModel):
    title: str = Field(min_length=1)
    sections: list[GeneratedLyricsSection] = Field(min_length=3, max_length=12)
    style_prompt: str = Field(min_length=1)

    @property
    def content(self) -> str:
        return "\n\n".join(
            f"[{section.name}]\n{section.content}" for section in self.sections
        )


class TextGenerationProvider(Protocol):
    name: str
    model: str | None

    def analyze(self, context: dict[str, Any]) -> ProviderResult[GeneratedAnalysis]: ...

    def generate_lyrics(
        self,
        context: dict[str, Any],
        variation: int,
    ) -> ProviderResult[GeneratedLyrics]: ...

    def test_connection(self) -> ProviderResult[dict[str, Any]]: ...


GENRE_SIGNALS = {
    "R&B": ("r&b", "r＆b", "蓝调"),
    "电子": ("dj", "电音", "remix", "舞曲"),
    "民谣": ("故乡", "远方", "吉他", "民谣"),
    "说唱": ("说唱", "rap", "rapper"),
    "摇滚": ("摇滚", "rock", "乐队"),
}
MOOD_SIGNALS = {
    "伤感": ("雨", "失眠", "告别", "遗憾", "孤独", "回忆", "再见", "错过"),
    "治愈": ("光", "风", "自由", "晴", "拥抱", "温柔"),
    "甜蜜": ("心动", "靠近", "喜欢", "爱", "浪漫"),
    "热烈": ("热烈", "青春", "燃", "夏", "狂欢"),
}
THEME_SIGNALS = {
    "爱情": ("爱", "心动", "喜欢", "恋", "靠近"),
    "告别": ("告别", "再见", "离开", "错过"),
    "成长": ("青春", "成长", "自由", "未来", "沿途"),
    "思念": ("回忆", "故乡", "想念", "来信", "梦"),
    "城市夜晚": ("城市", "夜", "失眠", "日落", "晚风"),
}


def _signal_counts(
    songs: list[dict[str, Any]], signals: dict[str, tuple[str, ...]]
) -> Counter[str]:
    counts: Counter[str] = Counter()
    for song in songs:
        value = f"{song.get('title', '')} {song.get('artist', '')}".lower()
        for label, keywords in signals.items():
            if any(keyword.lower() in value for keyword in keywords):
                counts[label] += 1
    return counts


def _top_labels(counts: Counter[str], fallback: list[str], limit: int = 3) -> list[str]:
    labels = [label for label, _ in counts.most_common(limit)]
    for fallback_label in fallback:
        if len(labels) >= limit:
            break
        if fallback_label not in labels:
            labels.append(fallback_label)
    return labels


class LocalTextProvider:
    name = "local"
    model = "rules-v1"

    def analyze(self, context: dict[str, Any]) -> ProviderResult[GeneratedAnalysis]:
        songs = list(context.get("songs") or [])
        metrics = dict(context.get("metrics") or {})
        genres = _top_labels(_signal_counts(songs, GENRE_SIGNALS), ["流行"], 2)
        moods = _top_labels(
            _signal_counts(songs, MOOD_SIGNALS), ["治愈", "伤感"], 3
        )
        themes = _top_labels(
            _signal_counts(songs, THEME_SIGNALS), ["爱情", "成长", "城市夜晚"], 4
        )
        days = int(metrics.get("available_days", 1))
        rising = int(metrics.get("rising_count", 0))
        new = int(metrics.get("new_count", 0))
        summary = (
            f"本次使用 {days} 个有效榜单日、{len(songs)} 首候选歌曲。"
            f"其中上升 {rising} 首、新出现 {new} 首。"
            "风格和情绪来自标题、歌手及排名变化的方向性推断，不代表音频检测结论。"
        )

        base_genres = genres or ["流行"]
        primary_mood = moods[0]
        primary_theme = themes[0]
        directions = [
            GeneratedDirection(
                name="主流情绪流行",
                genre_tags=base_genres,
                mood_tags=moods[:2],
                theme_keywords=themes[:3],
                scene_tags=["通勤", "夜晚独处"],
                tempo="medium",
                vocal_gender="unspecified",
                vocal_style="自然叙事，副歌情绪明显抬升",
                instrument_tags=["钢琴", "吉他", "流行鼓组", "弦乐铺底"],
                structure=["Intro", "Verse", "Pre Chorus", "Chorus", "Verse", "Chorus", "Bridge", "Outro"],
                hook_direction=f"围绕“{primary_theme}”设计一句短而可重复的副歌核心句",
                negative_constraints=["不要照搬榜单歌曲歌词", "不要声称复刻具体歌手"],
            ),
            GeneratedDirection(
                name="短视频记忆点",
                genre_tags=list(dict.fromkeys(["流行", "电子", *base_genres]))[:3],
                mood_tags=list(dict.fromkeys(["热烈", primary_mood]))[:2],
                theme_keywords=themes[:3],
                scene_tags=["短视频", "聚会", "驾车"],
                tempo="fast",
                vocal_gender="unspecified",
                vocal_style="节奏清楚，咬字直接，Hook 提前出现",
                instrument_tags=["合成器", "电子鼓", "低音贝斯", "拍手节奏"],
                structure=["Intro", "Hook", "Verse", "Chorus", "Break", "Chorus", "Outro"],
                hook_direction="前四十秒内出现核心句，使用短句和节奏性重复",
                negative_constraints=["避免堆砌网络热词", "避免过长前奏"],
            ),
            GeneratedDirection(
                name="慢速叙事表达",
                genre_tags=list(dict.fromkeys(["流行", "民谣", "R&B", *base_genres]))[:3],
                mood_tags=list(dict.fromkeys(["克制", "怀念", primary_mood]))[:3],
                theme_keywords=list(dict.fromkeys(["错过", "成长", *themes]))[:4],
                scene_tags=["深夜", "耳机聆听"],
                tempo="slow",
                vocal_gender="unspecified",
                vocal_style="贴近说话感，主歌克制，尾段释放",
                instrument_tags=["木吉他", "钢琴", "轻鼓组", "环境音色"],
                structure=["Intro", "Verse", "Verse", "Chorus", "Bridge", "Chorus", "Outro"],
                hook_direction="用具体生活画面铺陈，在副歌落到一句明确情绪判断",
                negative_constraints=["避免空泛口号", "避免生硬押韵"],
            ),
        ]
        return ProviderResult(
            output=GeneratedAnalysis(
                trend_summary=summary,
                creation_directions=directions,
            ),
            call=_local_call("analysis"),
        )

    def generate_lyrics(
        self,
        context: dict[str, Any],
        variation: int,
    ) -> ProviderResult[GeneratedLyrics]:
        theme = str(context.get("theme") or "一次没有说完的告别").strip()
        keywords = list(context.get("keywords") or [])
        moods = list(context.get("mood_tags") or ["克制", "温柔"])
        genres = list(context.get("genre_tags") or ["流行"])
        scenes = list(context.get("scene_tags") or ["夜晚"])
        keyword_a = keywords[0] if keywords else theme[:6]
        keyword_b = keywords[1] if len(keywords) > 1 else "回声"
        scene = scenes[0] if scenes else "夜晚"
        time_suffix = "以后" if variation % 2 == 0 else "以前"
        title = str(context.get("title_hint") or "").strip()
        if not title:
            title = f"{keyword_a}{time_suffix}"[:18]

        sections = [
            {
                "name": "Intro",
                "content": f"{scene}把灯一盏一盏点亮\n我听见{keyword_b}还留在远方",
            },
            {
                "name": "Verse",
                "content": (
                    f"走过熟悉的街口 人群换了方向\n"
                    f"关于{theme} 我练习若无其事地讲\n"
                    f"那些没寄出的句子 还折在旧时光\n"
                    f"风吹开一页 又轻轻替我合上"
                ),
            },
            {
                "name": "Pre Chorus",
                "content": (
                    f"如果{keyword_a}也有声音\n"
                    f"会不会替我承认 我还没有忘记"
                ),
            },
            {
                "name": "Chorus",
                "content": (
                    f"在{keyword_a}{time_suffix} 我还是我\n"
                    f"只是学会把想念 写得轻描淡写\n"
                    f"等城市安静 等最后一班车经过\n"
                    f"我终于能对昨天 说一声来过"
                ),
            },
            {
                "name": "Verse",
                "content": (
                    f"窗外的雨停下来 天空慢慢清澈\n"
                    f"原来有些答案 不必等谁认可\n"
                    f"我把遗憾留给路口 把勇气带着\n"
                    f"下一段旅程 也值得认真生活"
                ),
            },
            {
                "name": "Bridge",
                "content": (
                    f"不是所有故事 都要圆满才深刻\n"
                    f"谢谢那段沉默 让我听见真正的我"
                ),
            },
            {
                "name": "Outro",
                "content": f"当{keyword_b}散进风里\n我会带着{keyword_a}继续走下去",
            },
        ]
        style_parts = [
            *genres,
            *moods,
            str(context.get("tempo") or "medium"),
            str(context.get("vocal_style") or "自然叙事人声"),
        ]
        return ProviderResult(
            output=GeneratedLyrics(
                title=title,
                sections=sections,
                style_prompt=", ".join(part for part in style_parts if part),
            ),
            call=_local_call("lyrics"),
        )

    def test_connection(self) -> ProviderResult[dict[str, Any]]:
        return ProviderResult(
            output={"status": "ok"},
            call=_local_call("provider-test"),
        )


class OpenAICompatibleTextProvider:
    def __init__(self, config: TextProviderConfig | None = None) -> None:
        self.config = config or _environment_text_config()
        self.name = self.config.template_key
        if (
            not self.config.base_url
            or not self.config.api_key
            or not self.config.model
        ):
            raise TextProviderError(
                "当前 AI 接口缺少 Base URL、API Key 或模型名称"
            )
        if self.config.max_tokens_parameter not in {
            "max_tokens",
            "max_completion_tokens",
        }:
            raise TextProviderError("当前 AI 接口的最大 Token 参数不受支持")
        self.model = self.config.model

    def analyze(self, context: dict[str, Any]) -> ProviderResult[GeneratedAnalysis]:
        schema = json.dumps(
            GeneratedAnalysis.model_json_schema(),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        response = self._chat_json(
            system=(
                "你是音乐市场趋势分析助手。仅依据提供的榜单元数据和排名变化做方向性分析，"
                "不得声称检测了音频、准确BPM、调性、和弦或真实编曲。"
                "返回纯JSON，字段为 trend_summary 和 creation_directions；"
                "creation_directions 为1到3项，每项必须包含 name, language, genre_tags, "
                "mood_tags, theme_keywords, scene_tags, tempo(slow/medium/fast), "
                "vocal_gender(male/female/unspecified), vocal_style, instrument_tags, "
                "structure, hook_direction, negative_constraints。"
                "所有字符串字段必须返回字符串，数组字段必须返回数组，structure 至少3项。"
                f"必须严格匹配以下JSON Schema：{schema}"
            ),
            user=json.dumps(context, ensure_ascii=False),
            max_tokens=self.config.analysis_max_output_tokens,
            temperature=0.2,
        )
        try:
            output = GeneratedAnalysis.model_validate(response.output)
        except ValidationError as exc:
            raise TextProviderError(
                f"AI 分析结果字段不完整或类型不正确：{_validation_summary(exc)}",
                call=response.call,
            ) from exc
        return ProviderResult(output=output, call=response.call)

    def generate_lyrics(
        self,
        context: dict[str, Any],
        variation: int,
    ) -> ProviderResult[GeneratedLyrics]:
        payload = {**context, "variation": variation}
        schema = json.dumps(
            GeneratedLyrics.model_json_schema(),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        response = self._chat_json(
            system=(
                "你是中文原创作词助手。根据创作方案写一首可供音乐生成API使用的原创歌词。"
                "参考文本只能用于理解方向，不得复写或近似改写。返回纯JSON，字段为 title、"
                "style_prompt、sections；sections 每项包含 name 和 content，使用 Intro、Verse、"
                "Pre Chorus、Chorus、Bridge、Outro 等标准段落名。"
                f"必须严格匹配以下JSON Schema：{schema}"
            ),
            user=json.dumps(payload, ensure_ascii=False),
            max_tokens=self.config.lyrics_max_output_tokens,
            temperature=0.7,
        )
        try:
            output = GeneratedLyrics.model_validate(response.output)
        except ValidationError as exc:
            raise TextProviderError(
                f"AI 歌词结果字段不完整或类型不正确：{_validation_summary(exc)}",
                call=response.call,
            ) from exc
        return ProviderResult(output=output, call=response.call)

    def test_connection(self) -> ProviderResult[dict[str, Any]]:
        return self._chat_json(
            system='你正在执行接口连接测试。只返回 JSON：{"status":"ok"}。',
            user="连接测试",
            max_tokens=32,
            temperature=0.1,
        )

    def _chat_json(
        self,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
    ) -> ProviderResult[dict[str, Any]]:
        last_error: Exception | None = None
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        started_at = utc_now()
        attempts = max(1, self.config.max_retries)
        attempt_count = 0
        last_request_id: str | None = None
        last_call: ProviderCallMetadata | None = None
        for attempt in range(1, attempts + 1):
            attempt_count = attempt
            try:
                request_body: dict[str, Any] = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": temperature,
                }
                request_body[self.config.max_tokens_parameter] = max_tokens
                if self.config.supports_json_mode:
                    request_body["response_format"] = {"type": "json_object"}
                if _should_disable_thinking(url, self.model):
                    request_body["thinking"] = {"type": "disabled"}
                response = httpx.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self.config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=request_body,
                    timeout=self.config.request_timeout_seconds,
                )
                response.raise_for_status()
                body = response.json()
                last_request_id = str(body.get("request_id") or body.get("id") or "") or None
                completed_at = utc_now()
                usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
                input_tokens = _safe_int(usage.get("prompt_tokens"))
                output_tokens = _safe_int(usage.get("completion_tokens"))
                total_tokens = _safe_int(usage.get("total_tokens"))
                if not total_tokens:
                    total_tokens = input_tokens + output_tokens
                prompt_details = usage.get("prompt_tokens_details")
                cached_tokens = (
                    _safe_int(prompt_details.get("cached_tokens"))
                    if isinstance(prompt_details, dict)
                    else 0
                )
                last_call = ProviderCallMetadata(
                    method="POST",
                    endpoint=url,
                    is_external=True,
                    request_id=last_request_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    cached_tokens=cached_tokens,
                    usage_quantity=float(total_tokens),
                    attempt_count=attempt,
                    duration_ms=_duration_ms(started_at, completed_at),
                    raw_usage=usage or None,
                    started_at=started_at,
                    completed_at=completed_at,
                )
                content = body["choices"][0]["message"]["content"]
                decoded = _decode_json_object(content)
                return ProviderResult(output=decoded, call=last_call)
            except (
                httpx.HTTPError,
                IndexError,
                KeyError,
                TypeError,
                ValueError,
                json.JSONDecodeError,
            ) as exc:
                last_error = exc
                if isinstance(exc, httpx.HTTPStatusError):
                    last_request_id = (
                        _provider_request_id(exc.response) or last_request_id
                    )
                failure_summary = _provider_failure_summary(
                    exc,
                    timeout_seconds=self.config.request_timeout_seconds,
                )
                provider_logger.warning(
                    f"text_provider_attempt_failed: {failure_summary}",
                    extra={
                        "agent": self.name,
                        "step": "provider_request",
                        "attempt": attempt,
                        "status_code": _provider_status_code(exc),
                    },
                )
                if attempt < attempts and _should_retry_provider_error(exc):
                    time.sleep(_provider_retry_delay(exc, attempt))
                    continue
                break

        completed_at = utc_now()
        call = (
            replace(
                last_call,
                attempt_count=attempt_count,
                duration_ms=_duration_ms(started_at, completed_at),
                completed_at=completed_at,
            )
            if last_call is not None
            else ProviderCallMetadata(
                method="POST",
                endpoint=url,
                is_external=True,
                request_id=last_request_id,
                attempt_count=attempt_count,
                duration_ms=_duration_ms(started_at, completed_at),
                started_at=started_at,
                completed_at=completed_at,
            )
        )
        raise TextProviderError(
            _provider_final_error_message(
                last_error,
                attempt_count=attempt_count,
                timeout_seconds=self.config.request_timeout_seconds,
            ),
            call=call,
        ) from last_error


def _local_call(operation: str) -> ProviderCallMetadata:
    now = utc_now()
    return ProviderCallMetadata(
        method="EXECUTE",
        endpoint=f"local://rules-v1/{operation}",
        is_external=False,
        duration_ms=0,
        started_at=now,
        completed_at=now,
    )


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _provider_final_error_message(
    error: Exception | None,
    *,
    attempt_count: int,
    timeout_seconds: float,
) -> str:
    if error is None:
        summary = "AI 接口请求失败"
    else:
        summary = _provider_failure_summary(
            error,
            timeout_seconds=timeout_seconds,
        )
    if attempt_count > 1:
        return f"{summary}；已尝试 {attempt_count} 次"
    return summary


def _provider_failure_summary(
    error: Exception,
    *,
    timeout_seconds: float,
) -> str:
    if isinstance(error, httpx.TimeoutException):
        return f"AI 接口请求超时（单次等待上限 {_format_seconds(timeout_seconds)} 秒）"
    if isinstance(error, httpx.HTTPStatusError):
        status_code = error.response.status_code
        code, message = _provider_error_payload(error.response)
        details = ""
        if code and message:
            details = f"（{code}：{message}）"
        elif code:
            details = f"（{code}）"
        elif message:
            details = f"（{message}）"
        return f"AI 接口返回 HTTP {status_code}{details}"
    if isinstance(error, httpx.ConnectError):
        return "无法连接 AI 接口，请检查网络、域名和代理设置"
    if isinstance(error, httpx.NetworkError):
        return f"AI 接口网络异常（{type(error).__name__}）"
    if isinstance(error, httpx.HTTPError):
        return f"AI 接口 HTTP 通信异常（{type(error).__name__}）"
    if isinstance(error, json.JSONDecodeError):
        return "AI 接口响应不是有效 JSON"
    if isinstance(error, KeyError):
        missing = _safe_provider_text(str(error).strip("'\""), max_length=80)
        return f"AI 接口响应缺少字段：{missing or '未知字段'}"
    if isinstance(error, IndexError):
        return "AI 接口响应中没有可用的生成结果"
    if isinstance(error, TypeError):
        return "AI 接口响应字段类型不正确"
    if isinstance(error, ValueError):
        return "AI 接口返回的内容不是有效 JSON 对象"
    return f"AI 接口请求失败（{type(error).__name__}）"


def _provider_error_payload(response: httpx.Response) -> tuple[str | None, str | None]:
    try:
        body = response.json()
    except (TypeError, ValueError, json.JSONDecodeError):
        return None, None
    if not isinstance(body, dict):
        return None, None
    error = body.get("error")
    source = error if isinstance(error, dict) else body
    code = _safe_provider_text(source.get("code"), max_length=80)
    message = _safe_provider_text(source.get("message"), max_length=240)
    return code, message


def _provider_request_id(response: httpx.Response) -> str | None:
    for header_name in ("x-request-id", "x-zhipu-request-id", "request-id"):
        if value := response.headers.get(header_name):
            return _safe_provider_text(value, max_length=200)
    try:
        body = response.json()
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(body, dict):
        return None
    return _safe_provider_text(
        body.get("request_id") or body.get("id"),
        max_length=200,
    )


def _safe_provider_text(value: object, *, max_length: int) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).split())
    cleaned = redact_sensitive_values(cleaned)
    cleaned = re.sub(
        r"(?i)\b(?:api[ _-]?key|authorization)\b\s*[:=]?\s*\S+",
        "credential=***",
        cleaned,
    )
    cleaned = re.sub(r"(?i)\bbearer\s+[A-Za-z0-9._-]+", "Bearer ***", cleaned)
    return cleaned[:max_length] or None


def _provider_status_code(error: Exception) -> int | None:
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code
    return None


def _should_retry_provider_error(error: Exception) -> bool:
    if isinstance(error, httpx.HTTPStatusError):
        status_code = error.response.status_code
        if status_code == 429:
            return _provider_retry_after_seconds(error.response) is not None
        return status_code in {408, 409, 425} or status_code >= 500
    if isinstance(error, httpx.ReadTimeout):
        # The provider may still be generating after our connection stops waiting.
        # Retrying immediately can duplicate a paid call and consume its concurrency.
        return False
    return True


def _provider_retry_delay(error: Exception, attempt: int) -> float:
    if isinstance(error, httpx.HTTPStatusError):
        retry_after = _provider_retry_after_seconds(error.response)
        if retry_after is not None:
            return min(60.0, retry_after)
    return min(2.0, 0.5 * (2 ** max(0, attempt - 1)))


def _provider_retry_after_seconds(response: httpx.Response) -> float | None:
    retry_after = response.headers.get("retry-after")
    try:
        return max(0.0, float(retry_after)) if retry_after is not None else None
    except ValueError:
        return None


def _format_seconds(value: float) -> str:
    numeric = float(value)
    return str(int(numeric)) if numeric.is_integer() else f"{numeric:g}"


def _duration_ms(started_at: datetime, completed_at: datetime) -> int:
    return max(0, round((completed_at - started_at).total_seconds() * 1000))


def _decode_json_object(content: object) -> dict[str, Any]:
    if not isinstance(content, str):
        raise TypeError("response content is not text")
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
    candidates = [cleaned]
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        candidates.append(cleaned[first_brace : last_brace + 1])
    for candidate in candidates:
        try:
            decoded = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict):
            return decoded
    raise ValueError("response is not a JSON object")


def _validation_summary(exc: ValidationError) -> str:
    issues: list[str] = []
    for error in exc.errors(include_input=False)[:5]:
        location = ".".join(str(part) for part in error.get("loc", ())) or "response"
        issues.append(f"{location} ({error.get('type', 'invalid')})")
    return "、".join(issues) or "响应结构无效"


def _should_disable_thinking(endpoint: str, model: str | None) -> bool:
    hostname = (urlparse(endpoint).hostname or "").lower()
    model_name = (model or "").lower()
    return hostname.endswith("bigmodel.cn") and model_name.startswith(
        ("glm-4.7", "glm-5")
    )


def _environment_text_config() -> TextProviderConfig:
    return TextProviderConfig(
        template_key=settings.AI_PROVIDER,
        protocol="openai_compatible",
        base_url=settings.AI_BASE_URL,
        api_key=settings.AI_API_KEY,
        model=settings.AI_MODEL,
        request_timeout_seconds=settings.AI_REQUEST_TIMEOUT_SECONDS,
        max_retries=settings.AI_MAX_RETRIES,
        analysis_max_output_tokens=settings.AI_ANALYSIS_MAX_OUTPUT_TOKENS,
        lyrics_max_output_tokens=settings.AI_LYRICS_MAX_OUTPUT_TOKENS,
    )


def create_text_provider(config: TextProviderConfig) -> TextGenerationProvider:
    if config.protocol == "local":
        return LocalTextProvider()
    if config.protocol == "openai_compatible":
        return OpenAICompatibleTextProvider(config)
    raise TextProviderError(f"不支持的 AI 接口协议：{config.protocol}")


def get_text_provider() -> TextGenerationProvider:
    if settings.AI_PROVIDER == "local":
        return LocalTextProvider()
    if settings.AI_PROVIDER == "openai_compatible":
        return OpenAICompatibleTextProvider(_environment_text_config())
    raise TextProviderError(f"不支持的 AI_PROVIDER：{settings.AI_PROVIDER}")
