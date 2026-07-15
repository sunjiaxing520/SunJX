from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.ranking import TaskStatusValue


FavoriteItemType = Literal["analysis", "lyrics"]


class FavoriteCreateRequest(BaseModel):
    item_type: FavoriteItemType
    target_id: int = Field(ge=1)


class FavoriteNoteUpdate(BaseModel):
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("note")
    @classmethod
    def clean_note(cls, note: str | None) -> str | None:
        if note is None:
            return None
        cleaned = note.strip()
        return cleaned or None


class FavoriteItemResponse(BaseModel):
    id: int
    item_type: FavoriteItemType
    target_id: int
    source_task_id: int
    title: str
    summary: str
    status: TaskStatusValue
    provider: str
    model: str | None
    total_tokens: int
    source_created_at: datetime
    metadata: dict[str, object]
    note: str | None
    created_by_id: int | None
    created_by_username: str | None
    favorited_at: datetime
    updated_at: datetime


class FavoriteListResponse(BaseModel):
    items: list[FavoriteItemResponse]
    total: int
