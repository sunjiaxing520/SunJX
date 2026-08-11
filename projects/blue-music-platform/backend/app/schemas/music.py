from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.api_usage import ApiUsageResponse
from app.schemas.ranking import TaskStatusValue
from app.schemas.user import MusicTaskQuotaResponse


MusicOperationValue = Literal["generate", "extend"]
MusicProviderImplementationValue = Literal["official", "compatibility"]


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
    storage_backend: Literal["local", "s3"]
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
    provider_implementation: MusicProviderImplementationValue
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
    attempt_count: int
    max_attempts: int
    next_attempt_at: datetime | None
    last_queued_at: datetime | None
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


class MusicTaskRetryResponse(BaseModel):
    task: MusicTaskResponse


class SunoQuotaResponse(BaseModel):
    status: Literal["available", "error"]
    provider_implementation: MusicProviderImplementationValue
    credits_remaining: float | None
    usage: float | None
    quota_limit: float | None
    period: str | None
    error_code: str | None
    error_message: str | None
    checked_at: datetime


class SunoProviderStatusResponse(BaseModel):
    provider: Literal["suno"] = "suno"
    implementation: Literal["official", "compatibility", "invalid"]
    configured: bool
    integration_status: Literal[
        "waiting_access",
        "contract_pending",
        "disabled",
        "ready",
        "waiting_session",
        "unavailable",
        "configuration_error",
    ]
    message: str
    platform_url: str = "https://platform.suno.com/"
    queue_mode: Literal["redis", "inline"]
    max_concurrency: int
    min_request_interval_seconds: float
    user_quota: MusicTaskQuotaResponse
    quota: SunoQuotaResponse | None
