from typing import Literal

from pydantic import BaseModel

from app.models import AgentType


AgentRuntimeStatus = Literal["not_configured", "idle", "running", "failed"]


class DashboardMetrics(BaseModel):
    crawled_today: int
    analyzed_today: int
    lyrics_tasks_today: int
    music_tasks_today: int


class DashboardAgentStatus(BaseModel):
    agent: AgentType
    name: str
    status: AgentRuntimeStatus
    message: str


class DashboardResponse(BaseModel):
    metrics: DashboardMetrics
    agents: list[DashboardAgentStatus]
