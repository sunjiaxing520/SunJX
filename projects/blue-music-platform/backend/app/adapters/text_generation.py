import json
import re
import time
from collections import Counter
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings


class TextProviderError(RuntimeError):
    pass


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


class GeneratedLyrics(BaseModel):
    title: str
    sections: list[dict[str, str]] = Field(min_length=3, max_length=12)
    style_prompt: str

    @property
    def content(self) -> str:
        return "\n\n".join(
            f"[{section['name']}]\n{section['content']}" for section in self.sections
        )


class TextGenerationProvider(Protocol):
    name: str
    model: str | None

    def analyze(self, context: dict[str, Any]) -> GeneratedAnalysis: ...

    def generate_lyrics(
        self,
        context: dict[str, Any],
        variation: int,
    ) -> GeneratedLyrics: ...


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

    def analyze(self, context: dict[str, Any]) -> GeneratedAnalysis:
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
        return GeneratedAnalysis(
            trend_summary=summary,
            creation_directions=directions,
        )

    def generate_lyrics(
        self,
        context: dict[str, Any],
        variation: int,
    ) -> GeneratedLyrics:
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
        return GeneratedLyrics(
            title=title,
            sections=sections,
            style_prompt=", ".join(part for part in style_parts if part),
        )


class OpenAICompatibleTextProvider:
    name = "openai_compatible"

    def __init__(self) -> None:
        if not settings.AI_BASE_URL or not settings.AI_API_KEY or not settings.AI_MODEL:
            raise TextProviderError(
                "AI_PROVIDER 已设为 openai_compatible，但 AI_BASE_URL、AI_API_KEY 或 AI_MODEL 未配置"
            )
        self.model = settings.AI_MODEL

    def analyze(self, context: dict[str, Any]) -> GeneratedAnalysis:
        response = self._chat_json(
            system=(
                "你是音乐市场趋势分析助手。仅依据提供的榜单元数据和排名变化做方向性分析，"
                "不得声称检测了音频、准确BPM、调性、和弦或真实编曲。"
                "返回纯JSON，字段为 trend_summary 和 creation_directions；"
                "creation_directions 为1到3项，每项必须包含 name, language, genre_tags, "
                "mood_tags, theme_keywords, scene_tags, tempo(slow/medium/fast), "
                "vocal_gender(male/female/unspecified), vocal_style, instrument_tags, "
                "structure, hook_direction, negative_constraints。"
            ),
            user=json.dumps(context, ensure_ascii=False),
        )
        try:
            return GeneratedAnalysis.model_validate(response)
        except ValidationError as exc:
            raise TextProviderError("AI 分析结果字段不完整或类型不正确") from exc

    def generate_lyrics(
        self,
        context: dict[str, Any],
        variation: int,
    ) -> GeneratedLyrics:
        payload = {**context, "variation": variation}
        response = self._chat_json(
            system=(
                "你是中文原创作词助手。根据创作方案写一首可供音乐生成API使用的原创歌词。"
                "参考文本只能用于理解方向，不得复写或近似改写。返回纯JSON，字段为 title、"
                "style_prompt、sections；sections 每项包含 name 和 content，使用 Intro、Verse、"
                "Pre Chorus、Chorus、Bridge、Outro 等标准段落名。"
            ),
            user=json.dumps(payload, ensure_ascii=False),
        )
        try:
            return GeneratedLyrics.model_validate(response)
        except ValidationError as exc:
            raise TextProviderError("AI 歌词结果字段不完整或类型不正确") from exc

    def _chat_json(self, system: str, user: str) -> dict[str, Any]:
        last_error: Exception | None = None
        url = f"{settings.AI_BASE_URL}/chat/completions"
        for attempt in range(1, max(1, settings.AI_MAX_RETRIES) + 1):
            try:
                response = httpx.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {settings.AI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.7,
                    },
                    timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                body = response.json()
                content = body["choices"][0]["message"]["content"]
                cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
                decoded = json.loads(cleaned)
                if not isinstance(decoded, dict):
                    raise ValueError("response is not a JSON object")
                return decoded
            except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt <= settings.AI_MAX_RETRIES:
                    time.sleep(0.5 * attempt)

        raise TextProviderError("AI 服务请求失败或返回了无法解析的内容") from last_error


def get_text_provider() -> TextGenerationProvider:
    if settings.AI_PROVIDER == "local":
        return LocalTextProvider()
    if settings.AI_PROVIDER == "openai_compatible":
        return OpenAICompatibleTextProvider()
    raise TextProviderError(f"不支持的 AI_PROVIDER：{settings.AI_PROVIDER}")
