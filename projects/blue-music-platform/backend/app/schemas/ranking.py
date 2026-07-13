from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


TaskStatusValue = Literal["pending", "running", "completed", "failed"]


class CollectionCreateRequest(BaseModel):
    source_mode: Literal["live", "sample"] = "live"
    limit: int = Field(default=100, ge=1, le=500)
    snapshot_date: date | None = None


class CollectionTaskResponse(BaseModel):
    id: int
    platform: str
    chart_code: str
    chart_name: str
    source_mode: str
    snapshot_date: date
    status: TaskStatusValue
    snapshot_id: int | None
    item_count: int
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class RankingSnapshotResponse(BaseModel):
    id: int
    platform: str
    chart_code: str
    chart_name: str
    snapshot_date: date
    source_updated_date: date | None
    item_count: int
    collected_at: datetime


class RankingEntryResponse(BaseModel):
    id: int
    snapshot_id: int
    source_song_id: str
    title: str
    artist: str
    rank: int
    popularity: float | None
    cover_url: str | None
    source_url: str | None
    duration_seconds: int | None


class RankingEntryPage(BaseModel):
    items: list[RankingEntryResponse]
    total: int
    page: int
    page_size: int
