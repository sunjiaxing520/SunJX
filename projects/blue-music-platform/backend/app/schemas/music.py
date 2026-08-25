from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.api_usage import ApiUsageResponse
from app.schemas.ranking import TaskStatusValue
from app.schemas.user import MusicTaskQuotaResponse


MusicOperationValue = Literal["generate", "extend", "adapt"]
MusicProviderImplementationValue = Literal["official", "compatibility"]


class MusicCreateRequest(BaseModel):
    lyrics_version_id: int
    title: str | None = Field(default=None, max_length=200)
    style_prompt: str | None = Field(default=None, max_length=3000)
    style_tags: list[str] = Field(default_factory=list, max_length=20)
    instrumental: bool = False
    negative_tags: list[str] = Field(default_factory=list, max_length=20)
    requirements: str | None = Field(default=None, max_length=2000)

    @field_validator("lyrics_version_id")
    @classmethod
    def validate_lyrics_version_id(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("歌词版本编号必须是正整数")
        return value

    @field_validator("style_tags", "negative_tags")
    @classmethod
    def clean_tags(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            cleaned = value.strip()
            if cleaned and cleaned not in result:
                result.append(cleaned[:80])
        return result

    @model_validator(mode="after")
    def prevent_conflicting_tags(self) -> "MusicCreateRequest":
        conflicts = sorted(set(self.style_tags) & set(self.negative_tags))
        if conflicts:
            raise ValueError(f"目标风格和排除风格不能重复：{'、'.join(conflicts)}")
        return self


class MusicReferenceSongResponse(BaseModel):
    entry_id: int
    source_song_id: str
    title: str
    artist: str
    cover_url: str | None
    source_url: str | None
    duration_seconds: int | None
    chart_name: str
    snapshot_date: date
    rank: int


class MusicReferenceSongListResponse(BaseModel):
    items: list[MusicReferenceSongResponse]
    total: int


class MusicReferenceRunCreateRequest(BaseModel):
    source_entry_id: int = Field(gt=0)
    instruction: str | None = Field(default=None, max_length=2000)

    @field_validator("instruction")
    @classmethod
    def clean_instruction(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class MusicExtendRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    lyrics: str | None = Field(default=None, max_length=5000)
    style_prompt: str | None = Field(default=None, max_length=3000)
    requirements: str | None = Field(default=None, max_length=2000)


class MusicAdaptRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    lyrics: str | None = Field(default=None, max_length=5000)
    style_prompt: str | None = Field(default=None, max_length=3000)
    style_tags: list[str] = Field(default_factory=list, max_length=20)
    negative_tags: list[str] = Field(default_factory=list, max_length=20)
    requirements: str | None = Field(default=None, max_length=2000)
    adaptation_mode: Literal["extend", "recreate"] = "extend"
    source_artist: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=2000)
    rights_confirmed: bool = False
    rights_note: str | None = Field(default=None, max_length=1000)

    @field_validator("style_tags", "negative_tags")
    @classmethod
    def clean_tags(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            cleaned = value.strip()
            if cleaned and cleaned not in result:
                result.append(cleaned[:80])
        return result

    @model_validator(mode="after")
    def validate_authorized_adaptation(self) -> "MusicAdaptRequest":
        conflicts = sorted(set(self.style_tags) & set(self.negative_tags))
        if conflicts:
            raise ValueError(f"目标风格和排除风格不能重复：{'、'.join(conflicts)}")
        if not self.rights_confirmed:
            raise ValueError("请确认已取得源作品的使用或改编授权")
        return self


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
    task_operation: MusicOperationValue
    task_model: str | None
    style_tags: list[str]
    negative_tags: list[str]
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
    style_tags: list[str]
    instrumental: bool
    negative_tags: list[str]
    requirements: str | None
    adaptation_mode: Literal["extend", "recreate"] | None
    source_title: str | None
    source_artist: str | None
    source_url: str | None
    rights_confirmed: bool
    rights_note: str | None
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


class MusicProviderSettingsResponse(BaseModel):
    active_model: str
    updated_by_id: int | None
    updated_at: datetime


class MusicProviderSettingsUpdate(BaseModel):
    active_model: str = Field(min_length=1, max_length=100)

    @field_validator("active_model")
    @classmethod
    def clean_model(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("请输入模型名称")
        return cleaned


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
    runtime_status: str | None = None
    captcha_mode: str | None = None
    cookie_configured: bool | None = None
    compat_routes: list[str] = Field(default_factory=list)
    queue_mode: Literal["redis", "inline"]
    max_concurrency: int
    min_request_interval_seconds: float
    active_model: str
    active_model_updated_at: datetime | None
    user_quota: MusicTaskQuotaResponse
    quota: SunoQuotaResponse | None
