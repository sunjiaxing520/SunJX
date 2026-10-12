from datetime import timedelta

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.time import utc_now
from app.models import MusicTask, TaskStatus, User, WorkflowRun, WorkflowRunStep


ACCOUNT_TASK_LIMIT = 2
ACTIVE_STATUSES = ("pending", "running", "paused")


def expire_paused_workflows(db: Session) -> int:
    cutoff = utc_now() - timedelta(days=2)
    runs = db.scalars(select(WorkflowRun).where(
        WorkflowRun.status == TaskStatus.PAUSED.value,
        WorkflowRun.updated_at < cutoff,
    ).with_for_update()).all()
    for run in runs:
        db.delete(run)
    if runs:
        db.commit()
    return len(runs)


def standalone_music_condition():
    return ~exists(select(WorkflowRunStep.id).join(WorkflowRun).where(
        WorkflowRunStep.step_type == "music",
        WorkflowRunStep.task_id == MusicTask.id,
        WorkflowRun.status.in_(ACTIVE_STATUSES),
    ))


def ensure_account_task_capacity(db: Session, user_id: int) -> None:
    db.execute(select(User.id).where(User.id == user_id).with_for_update()).first()
    workflow_count = db.scalar(select(func.count(WorkflowRun.id)).where(
        WorkflowRun.requested_by_id == user_id,
        WorkflowRun.status.in_(ACTIVE_STATUSES),
    )) or 0
    music_count = db.scalar(select(func.count(MusicTask.id)).where(
        MusicTask.requested_by_id == user_id,
        MusicTask.status.in_(("pending", "running")),
        standalone_music_condition(),
    )) or 0
    if workflow_count + music_count >= ACCOUNT_TASK_LIMIT:
        raise AppException(
            code="ACCOUNT_TASK_QUEUE_FULL",
            message="当前账号已有两个未完成任务，请等待完成或处理暂停审核后再提交",
            status_code=409,
            detail={"limit": ACCOUNT_TASK_LIMIT, "active_count": workflow_count + music_count},
        )


def account_task_queue(db: Session, user_id: int) -> dict:
    expire_paused_workflows(db)
    workflows = db.scalars(select(WorkflowRun).where(
        WorkflowRun.status.in_(ACTIVE_STATUSES),
    ).order_by(WorkflowRun.created_at, WorkflowRun.id)).all()
    music = db.scalars(select(MusicTask).where(
        MusicTask.status.in_(("pending", "running")), standalone_music_condition(),
    ).order_by(MusicTask.created_at, MusicTask.id)).all()
    items = []
    workflow_position = 0
    for run in workflows:
        if run.status == "pending":
            workflow_position += 1
        if run.requested_by_id == user_id:
            items.append({
                "kind": "workflow", "id": run.id, "title": run.template_name,
                "status": run.status, "position": workflow_position if run.status == "pending" else None,
                "created_at": run.created_at, "current_step": run.current_step,
                "expires_at": run.updated_at + timedelta(days=2) if run.status == "paused" else None,
            })
    music_position = 0
    for task in music:
        is_waiting = task.status == "pending" and not task.provider_submitted_at
        if is_waiting:
            music_position += 1
        if task.requested_by_id == user_id:
            items.append({
                "kind": "music", "id": task.id, "title": task.title,
                "status": "pending" if is_waiting else "running",
                "position": music_position if is_waiting else None,
                "created_at": task.created_at, "current_step": "music", "expires_at": None,
            })
    return {"limit": ACCOUNT_TASK_LIMIT, "active_count": len(items), "items": items}
