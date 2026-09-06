from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


LyricsMemoryCategory = Literal[
    "preference",
    "technique",
    "result",
    "pattern",
    "highlight",
]


class LyricsMemoryItemResponse(BaseModel):
    category: LyricsMemoryCategory
    content: str
    evidence_count: int = Field(ge=1)


class LyricsTeamMemoryResponse(BaseModel):
    items: list[LyricsMemoryItemResponse]
    total_items: int
    injection_limit: int
    source_count: int
    revision: int
    updated_by_id: int | None
    updated_at: datetime


class LyricsMemorySettingsRequest(BaseModel):
    injection_limit: int = Field(ge=1, le=200)


class LyricsMemoryChatRequest(BaseModel):
    instruction: str = Field(min_length=2, max_length=2000)

    @field_validator("instruction", mode="before")
    @classmethod
    def clean_instruction(cls, value: str) -> str:
        return value.strip()


class LyricsMemoryChatMessageResponse(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    is_applied: bool
    provider: str | None
    model: str | None
    created_by_id: int | None
    created_at: datetime
    applied_at: datetime | None


class LyricsMemoryChatListResponse(BaseModel):
    items: list[LyricsMemoryChatMessageResponse]


class LyricsMemoryChatResultResponse(BaseModel):
    message: LyricsMemoryChatMessageResponse
    memory: LyricsTeamMemoryResponse
