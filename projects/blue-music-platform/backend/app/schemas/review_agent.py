from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ReviewChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content")
    @classmethod
    def clean_content(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("内容不能为空")
        return cleaned


class ReviewAgentInitializationPreviewRequest(BaseModel):
    messages: list[ReviewChatMessage] = Field(default_factory=list, max_length=20)
    message: str = Field(min_length=1, max_length=4000)


class ReviewMemoryResponse(BaseModel):
    summary: str
    detail: dict[str, object] | None


class ReviewAgentInitializationPreviewResponse(ReviewMemoryResponse):
    reply: str


class ReviewAgentCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    initialization_messages: list[ReviewChatMessage] = Field(min_length=1, max_length=20)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("请输入审核智能体名称")
        return cleaned


class ReviewAgentMemberResponse(BaseModel):
    id: int
    username: str


class ReviewAgentResponse(BaseModel):
    id: int
    name: str
    initialization_notes: str | None
    memory_summary: str
    memory_detail: dict[str, object] | None
    created_by_id: int | None
    members: list[ReviewAgentMemberResponse]
    created_at: datetime
    updated_at: datetime


class ReviewAgentMemberUpdate(BaseModel):
    user_ids: list[int] = Field(default_factory=list, max_length=100)

    @field_validator("user_ids")
    @classmethod
    def clean_user_ids(cls, values: list[int]) -> list[int]:
        if any(value <= 0 for value in values):
            raise ValueError("成员编号必须是正整数")
        return list(dict.fromkeys(values))


class ReviewLyricsOption(BaseModel):
    id: int
    task_id: int
    version_number: int
    title: str
    created_at: datetime


class ReviewCreateRequest(BaseModel):
    lyrics_version_id: int = Field(gt=0)
    instruction: str | None = Field(default=None, max_length=2000)


class ReviewResultResponse(BaseModel):
    id: int
    agent_id: int
    lyrics_version_id: int | None
    requested_by_id: int | None
    instruction: str | None
    provider: str
    model: str | None
    result: dict[str, object]
    created_at: datetime


class ReviewListResponse(BaseModel):
    items: list[ReviewResultResponse]
    total: int


class ReviewMemorySaveRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content")
    @classmethod
    def clean_content(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("请输入要保存的记忆")
        return cleaned
