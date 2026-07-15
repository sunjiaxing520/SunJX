from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.api_usage import ApiUsageResponse
from app.schemas.ranking import TaskStatusValue


class AnalysisCreateRequest(BaseModel):
    entry_ids: list[int] = Field(default_factory=list, max_length=100)
    window_days: int = Field(default=7, ge=1, le=30)


class CreationDirection(BaseModel):
    name: str
    language: str = "中文"
    genre_tags: list[str]
    mood_tags: list[str]
    theme_keywords: list[str]
    scene_tags: list[str]
    tempo: Literal["slow", "medium", "fast"]
    vocal_gender: Literal["male", "female", "unspecified"]
    vocal_style: str
    instrument_tags: list[str]
    structure: list[str]
    hook_direction: str
    negative_constraints: list[str]


class AnalysisReportResponse(BaseModel):
    id: int
    task_id: int
    trend_summary: str
    trend_metrics: dict[str, object]
    creation_directions: list[CreationDirection]
    evidence: dict[str, object]
    created_at: datetime


class AnalysisTaskResponse(BaseModel):
    id: int
    status: TaskStatusValue
    provider: str
    model: str | None
    window_days: int
    window_start: date
    window_end: date
    selected_entry_count: int
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    api_usage: list[ApiUsageResponse]
    report: AnalysisReportResponse | None


class AnalysisTaskListResponse(BaseModel):
    items: list[AnalysisTaskResponse]
    total: int
