import re

from app.core.exceptions import AppException


LYRICS_PROMPT_REJECTED_CODE = "LYRICS_PROMPT_IRRELEVANT"

_NOISE_ONLY = {
    "test",
    "hi",
    "hello",
    "thanks",
    "thankyou",
    "你好",
    "您好",
    "哈喽",
    "嗨",
    "在吗",
    "你在吗",
    "好的",
    "好",
    "谢谢",
    "多谢",
    "收到",
    "测试",
    "测试一下",
    "试一下",
    "随便",
    "继续",
    "没了",
    "辛苦了",
    "早上好",
    "下午好",
    "晚上好",
    "晚安",
    "再见",
}

_CHATTER_MARKERS = (
    "今天天气怎么样",
    "天气怎么样",
    "天气好吗",
    "吃饭了吗",
    "你在干嘛",
    "你是谁",
    "你叫什么",
    "你好吗",
    "你能做什么",
    "陪我聊天",
    "陪我聊聊",
    "聊聊天",
    "讲个笑话",
    "最近怎么样",
    "howareyou",
    "whatcanyoudo",
    "tellmeajoke",
)

_LYRICS_MARKERS = (
    "歌词",
    "歌曲",
    "歌名",
    "作词",
    "创作",
    "写一首",
    "写首",
    "改",
    "修改",
    "重写",
    "优化",
    "润色",
    "副歌",
    "主歌",
    "押韵",
    "韵脚",
    "节奏",
    "风格",
    "曲风",
    "情绪",
    "主题",
    "氛围",
    "故事",
    "画面",
    "人声",
    "段落",
    "结构",
    "表达",
    "句子",
    "字数",
    "口语",
    "记忆点",
    "保留",
    "删除",
    "删掉",
    "增加",
    "避免",
    "不要",
    "短一点",
    "长一点",
    "更有",
    "更像",
    "换成",
    "改成",
    "song",
    "lyrics",
    "chorus",
    "verse",
    "rhyme",
    "rewrite",
    "revise",
)

_POLITE_ONLY_PATTERN = re.compile(
    r"^(?:你好|您好|哈喽|嗨|谢谢|多谢|好的|好|收到|嗯+|哦+|啊+|哈哈+|呵呵+|辛苦了|再见)+$"
)


def screen_lyrics_prompt(
    value: str,
    *,
    field_name: str,
    allow_short_topic: bool = False,
) -> str:
    """Reject obvious chatter before it can create tasks or memory evidence."""

    cleaned = _clean_prompt(value)
    compact = _compact_prompt(cleaned)
    has_lyrics_marker = any(marker in compact for marker in _LYRICS_MARKERS)
    is_chatter = (
        not compact
        or compact in _NOISE_ONLY
        or _POLITE_ONLY_PATTERN.fullmatch(compact) is not None
        or (
            any(marker in compact for marker in _CHATTER_MARKERS)
            and not has_lyrics_marker
        )
        or (
            not allow_short_topic
            and len(compact) == 1
            and not has_lyrics_marker
        )
    )
    if is_chatter:
        raise AppException(
            code=LYRICS_PROMPT_REJECTED_CODE,
            message=(
                "这段内容与歌词创作无关，已停止提交。请不要输入闲聊，"
                "直接说明歌曲主题、风格、情绪，或需要修改的具体内容。"
            ),
            status_code=422,
            detail={"field": field_name},
        )
    return cleaned


def screen_optional_lyrics_prompt(
    value: str | None,
    *,
    field_name: str,
) -> str | None:
    if value is None or not value.strip():
        return None
    return screen_lyrics_prompt(value, field_name=field_name)


def _clean_prompt(value: str) -> str:
    normalized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
    return "\n".join(
        line
        for raw_line in normalized.splitlines()
        if (line := re.sub(r"[ \t]+", " ", raw_line).strip())
    ).strip()


def _compact_prompt(value: str) -> str:
    return re.sub(r"[^0-9a-z\u3400-\u9fff]+", "", value.casefold())
