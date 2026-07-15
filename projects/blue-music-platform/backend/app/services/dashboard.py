from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AgentType,
    AnalysisTask,
    CollectionTask,
    LyricsTask,
    RankingSnapshot,
    TaskStatus,
    User,
    UserAgentPermission,
    UserRole,
)
from app.core.time import app_today, utc_day_bounds
from app.schemas.dashboard import (
    DashboardAgentStatus,
    DashboardMetrics,
    DashboardResponse,
)
from app.services.api_usage import get_api_usage_dashboard


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
    agents = [_agent_status(db, agent) for agent in _available_agents(db, user)]
    today = app_today()

    return DashboardResponse(
        metrics=DashboardMetrics(
            crawled_today=int(
                db.scalar(
                    select(func.coalesce(func.sum(RankingSnapshot.item_count), 0)).where(
                        RankingSnapshot.snapshot_date == today
                    )
                )
                or 0
            ),
            analyzed_today=_completed_task_count(db, AnalysisTask, today),
            lyrics_tasks_today=_completed_task_count(db, LyricsTask, today),
            music_tasks_today=0,
        ),
        agents=agents,
        api_usage=get_api_usage_dashboard(
            db,
            include_balance=user.role == UserRole.SUPER_ADMIN,
        ),
    )


def _completed_task_count(db: Session, model, today: date) -> int:
    day_start, day_end = utc_day_bounds(today)
    return int(
        db.scalar(
            select(func.count(model.id)).where(
                model.completed_at >= day_start,
                model.completed_at < day_end,
                model.status == TaskStatus.COMPLETED.value,
            )
        )
        or 0
    )


def _agent_status(db: Session, agent: AgentType) -> DashboardAgentStatus:
    model_by_agent = {
        AgentType.CRAWLER: CollectionTask,
        AgentType.ANALYSIS: AnalysisTask,
        AgentType.LYRICS: LyricsTask,
    }
    model = model_by_agent.get(agent)
    if model is None:
        return DashboardAgentStatus(
            agent=agent,
            name=AGENT_NAMES[agent],
            status="not_configured",
            message="等待音乐生成平台选型",
        )

    latest = db.scalar(select(model).order_by(model.id.desc()).limit(1))
    if latest is None:
        return DashboardAgentStatus(
            agent=agent,
            name=AGENT_NAMES[agent],
            status="idle",
            message="已就绪，暂无运行记录",
        )
    if latest.status in {TaskStatus.PENDING.value, TaskStatus.RUNNING.value}:
        status = "running"
        message = f"任务 #{latest.id} 正在运行"
    elif latest.status == TaskStatus.FAILED.value:
        status = "failed"
        message = latest.error_message or f"任务 #{latest.id} 运行失败"
    else:
        status = "idle"
        message = f"最近任务 #{latest.id} 已完成"
    return DashboardAgentStatus(
        agent=agent,
        name=AGENT_NAMES[agent],
        status=status,
        message=message,
    )
