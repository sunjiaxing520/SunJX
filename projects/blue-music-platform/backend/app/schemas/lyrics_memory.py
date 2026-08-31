from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


LyricsMemoryEventType = Literal[
    "creation_request",
    "modification_request",
    "accepted_result",
    "ranking_lyrics_insight",
    "admin_rule",
]


class LyricsMemoryEventSummaryResponse(BaseModel):
    id: int
    event_type: LyricsMemoryEventType
    task_id: int | None
    source_version_id: int | None
    created_by_id: int | None
    created_by_username: str | None
    content_preview: str
    context_preview: dict[str, Any]
    is_useful: bool
    created_at: datetime


class LyricsMemoryEventDetailResponse(LyricsMemoryEventSummaryResponse):
    raw_content: str
    cleaned_content: str
    context: dict[str, Any]


class LyricsMemoryEventListResponse(BaseModel):
    items: list[LyricsMemoryEventSummaryResponse]
    total: int
    page: int
    page_size: int


class LyricsMemoryOverviewResponse(BaseModel):
    total_events: int
    active_events: int
    inactive_events: int
    category_counts: dict[str, int]
    last_updated_at: datetime | None
    capsule_char_count: int


class LyricsMemoryPreviewResponse(BaseModel):
    capsule_char_count: int
    memory: dict[str, Any]


class LyricsMemoryUsefulnessRequest(BaseModel):
    is_useful: bool


class LyricsMemoryManualRuleRequest(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=2, max_length=2000)

    @field_validator("title", "content", mode="before")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.strip()


class LyricsMemoryBulkDeleteRequest(BaseModel):
    event_ids: list[int] = Field(min_length=1, max_length=100)

    @field_validator("event_ids")
    @classmethod
    def clean_event_ids(cls, event_ids: list[int]) -> list[int]:
        if any(event_id <= 0 for event_id in event_ids):
            raise ValueError("记忆编号必须是正整数")
        return list(dict.fromkeys(event_ids))


class LyricsMemoryDeleteResponse(BaseModel):
    deleted_count: int
    deleted_event_ids: list[int]


LyricsMemoryOperationType = Literal[
    "add_rule",
    "update_rule",
    "disable_event",
    "enable_event",
]


class LyricsMemoryOperationResponse(BaseModel):
    action: LyricsMemoryOperationType
    event_id: int | None
    title: str | None
    content: str | None
    reason: str


class LyricsMemoryProposalResponse(BaseModel):
    reply: str
    operations: list[LyricsMemoryOperationResponse]


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
    proposal: LyricsMemoryProposalResponse | None
    is_applied: bool
    provider: str | None
    model: str | None
    created_by_id: int | None
    created_at: datetime
    applied_at: datetime | None


class LyricsMemoryChatListResponse(BaseModel):
    items: list[LyricsMemoryChatMessageResponse]


class LyricsMemoryApplyResponse(BaseModel):
    message: LyricsMemoryChatMessageResponse
    created_event_ids: list[int]
    updated_event_ids: list[int]


class LyricsMemorySnapshotCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()


class LyricsMemorySnapshotUpdateRequest(LyricsMemorySnapshotCreateRequest):
    pass


class LyricsMemorySnapshotSummaryResponse(BaseModel):
    id: int
    name: str
    source_event_count: int
    capsule_char_count: int
    created_by_id: int | None
    created_at: datetime
    updated_at: datetime


class LyricsMemorySnapshotDetailResponse(LyricsMemorySnapshotSummaryResponse):
    memory: dict[str, Any]


class LyricsMemorySnapshotListResponse(BaseModel):
    items: list[LyricsMemorySnapshotSummaryResponse]
    total: int
    limit: int = 20
