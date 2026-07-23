from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.api_usage import ApiUsageResponse
from app.schemas.ranking import TaskStatusValue


MusicOperationValue = Literal["generate", "extend"]


class MusicCreateRequest(BaseModel):
    lyrics_version_id: int
    title: str | None = Field(default=None, max_length=200)
    style_prompt: str | None = Field(default=None, max_length=3000)
    instrumental: bool = False
    negative_tags: list[str] = Field(default_factory=list, max_length=20)
    requirements: str | None = Field(default=None, max_length=2000)

    @field_validator("lyrics_version_id")
    @classmethod
    def validate_lyrics_version_id(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("歌词版本编号必须是正整数")
        return value

    @field_validator("negative_tags")
    @classmethod
    def clean_negative_tags(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            cleaned = value.strip()
            if cleaned and cleaned not in result:
                result.append(cleaned[:80])
        return result


class MusicExtendRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    lyrics: str | None = Field(default=None, max_length=5000)
    style_prompt: str | None = Field(default=None, max_length=3000)
    requirements: str | None = Field(default=None, max_length=2000)


class MusicResultResponse(BaseModel):
    id: int
    task_id: int
    external_id: str
    title: str
    media_type: str
    duration_seconds: int | None
    image_url: str | None
    provider_page_url: str | None
    storage_error: str | None
    audio_ready: bool
    audio_path: str
    download_path: str
    created_at: datetime


class MusicTaskResponse(BaseModel):
    id: int
    status: TaskStatusValue
    operation: MusicOperationValue
    provider: Literal["suno"]
    model: str | None
    lyrics_version_id: int | None
    source_result_id: int | None
    title: str
    lyrics: str
    style_prompt: str
    instrumental: bool
    negative_tags: list[str]
    requirements: str | None
    external_task_id: str | None
    provider_status: str | None
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    api_usage: list[ApiUsageResponse]
    results: list[MusicResultResponse]


class MusicTaskListResponse(BaseModel):
    items: list[MusicTaskResponse]
    total: int


class MusicResultListResponse(BaseModel):
    items: list[MusicResultResponse]
    total: int


class MusicTaskDeleteRequest(BaseModel):
    task_ids: list[int] = Field(min_length=1, max_length=100)

    @field_validator("task_ids")
    @classmethod
    def clean_task_ids(cls, task_ids: list[int]) -> list[int]:
        if any(task_id <= 0 for task_id in task_ids):
            raise ValueError("任务编号必须是正整数")
        return list(dict.fromkeys(task_ids))


class MusicTaskDeleteResponse(BaseModel):
    deleted_count: int
    deleted_task_ids: list[int]


class SunoProviderStatusResponse(BaseModel):
    provider: Literal["suno"] = "suno"
    configured: bool
    integration_status: Literal["waiting_access", "contract_pending"]
    message: str
    platform_url: str = "https://platform.suno.com/"
