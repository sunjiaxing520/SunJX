import pytest

from app.core.exceptions import AppException
from app.services.lyrics_prompt import (
    LYRICS_PROMPT_REJECTED_CODE,
    screen_lyrics_prompt,
    screen_optional_lyrics_prompt,
)


@pytest.mark.parametrize(
    "value",
    ["你好", "谢谢", "今天天气怎么样", "你能做什么", "哈哈哈哈"],
)
def test_screen_lyrics_prompt_rejects_obvious_chatter(value: str) -> None:
    with pytest.raises(AppException) as caught:
        screen_lyrics_prompt(value, field_name="歌词修改要求")

    assert caught.value.code == LYRICS_PROMPT_REJECTED_CODE
    assert caught.value.status_code == 422
    assert caught.value.detail == {"field": "歌词修改要求"}


@pytest.mark.parametrize(
    ("value", "allow_short_topic"),
    [
        ("爱情", True),
        ("你好，请帮我写一首关于失恋的歌，谢谢", False),
        ("副歌再短一点，更有记忆点", False),
        ("我失恋了", False),
    ],
)
def test_screen_lyrics_prompt_accepts_creation_and_revision_requirements(
    value: str,
    allow_short_topic: bool,
) -> None:
    result = screen_lyrics_prompt(
        value,
        field_name="歌词要求",
        allow_short_topic=allow_short_topic,
    )

    assert result == value


def test_screen_optional_lyrics_prompt_keeps_empty_value_optional() -> None:
    assert screen_optional_lyrics_prompt(None, field_name="补充要求") is None
    assert screen_optional_lyrics_prompt("   ", field_name="补充要求") is None


def test_screen_lyrics_prompt_normalizes_whitespace_and_control_characters() -> None:
    result = screen_lyrics_prompt(
        "  副歌\t再短一点\x00\n\n  保留第一句  ",
        field_name="歌词修改要求",
    )

    assert result == "副歌 再短一点\n保留第一句"
