from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AgentType, User, UserAgentPermission, UserRole
from app.schemas.dashboard import (
    DashboardAgentStatus,
    DashboardMetrics,
    DashboardResponse,
)


AGENT_NAMES = {
    AgentType.CRAWLER: "榜单采集 Agent",
    AgentType.ANALYSIS: "内容分析 Agent",
    AgentType.LYRICS: "歌词创作 Agent",
    AgentType.MUSIC: "音乐创作 Agent",
}


def _available_agents(db: Session, user: User) -> list[AgentType]:
    if user.role == UserRole.SUPER_ADMIN:
        return list(AgentType)

    return list(
        db.scalars(
            select(UserAgentPermission.agent)
            .where(UserAgentPermission.user_id == user.id)
            .order_by(UserAgentPermission.agent)
        ).all()
    )


def get_dashboard(db: Session, user: User) -> DashboardResponse:
    agents = [
        DashboardAgentStatus(
            agent=agent,
            name=AGENT_NAMES[agent],
            status="not_configured",
            message="尚未配置执行器",
        )
        for agent in _available_agents(db, user)
    ]

    return DashboardResponse(
        metrics=DashboardMetrics(
            crawled_today=0,
            analyzed_today=0,
            lyrics_tasks_today=0,
            music_tasks_today=0,
        ),
        agents=agents,
    )
