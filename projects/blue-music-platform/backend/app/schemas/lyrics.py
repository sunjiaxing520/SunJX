from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.api_usage import ApiUsageResponse
from app.schemas.ranking import TaskStatusValue


class LyricsCreateRequest(BaseModel):
    analysis_report_id: int | None = None
    direction_index: int | None = Field(default=None, ge=0, le=9)
    title_hint: str | None = Field(default=None, max_length=200)
    theme: str = Field(min_length=1, max_length=500)
    language: str = Field(default="中文", min_length=1, max_length=30)
    genre_tags: list[str] = Field(default_factory=list, max_length=10)
    mood_tags: list[str] = Field(default_factory=list, max_length=10)
    scene_tags: list[str] = Field(default_factory=list, max_length=10)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    tempo: Literal["slow", "medium", "fast"] | None = None
    vocal_gender: Literal["male", "female", "unspecified"] | None = None
    vocal_style: str | None = Field(default=None, max_length=200)
    requirements: str | None = Field(default=None, max_length=2000)
    reference_text: str | None = Field(default=None, max_length=3000)

    @field_validator("genre_tags", "mood_tags", "scene_tags", "keywords")
    @classmethod
    def clean_tags(cls, tags: list[str]) -> list[str]:
        result: list[str] = []
        for tag in tags:
            cleaned = tag.strip()
            if cleaned and cleaned not in result:
                result.append(cleaned[:50])
        return result


class LyricsVersionResponse(BaseModel):
    id: int
    task_id: int
    version_number: int
    title: str
    content: str
    style_prompt: str
    sections: list[dict[str, str]]
    is_saved: bool
    created_at: datetime


class LyricsTaskResponse(BaseModel):
    id: int
    status: TaskStatusValue
    provider: str
    model: str | None
    analysis_report_id: int | None
    direction_index: int | None
    title_hint: str | None
    theme: str
    language: str
    genre_tags: list[str]
    mood_tags: list[str]
    scene_tags: list[str]
    keywords: list[str]
    tempo: str | None
    vocal_gender: str | None
    vocal_style: str | None
    requirements: str | None
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    api_usage: list[ApiUsageResponse]
    versions: list[LyricsVersionResponse]


class LyricsTaskListResponse(BaseModel):
    items: list[LyricsTaskResponse]
    total: int


class CreationBriefResponse(BaseModel):
    title: str
    creation_type: Literal["vocal"] = "vocal"
    language: str
    genre_tags: list[str]
    mood_tags: list[str]
    theme_keywords: list[str]
    scene_tags: list[str]
    tempo: str
    vocal_gender: str
    vocal_style: str
    instrument_tags: list[str]
    structure: list[str]
    hook_direction: str
    lyrics: str
    negative_constraints: list[str]
    source_analysis_report_id: int | None
    source_lyrics_version_id: int
