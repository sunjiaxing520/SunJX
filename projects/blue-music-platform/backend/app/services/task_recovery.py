import logging
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import LOGGER_NAME
from app.core.time import utc_now
from app.models import (
    AiProviderConfig,
    AnalysisTask,
    LyricsTask,
    MusicTask,
    TaskStatus,
)


task_logger = logging.getLogger(f"{LOGGER_NAME}.tasks")
TEXT_TASK_GRACE_SECONDS = 60.0


def recover_stale_text_tasks(db: Session) -> int:
    """Fail in-process text tasks that have outlived every configured attempt."""

    max_runtime_seconds = _text_task_max_runtime_seconds(db)
    now = utc_now()
    cutoff = now - timedelta(seconds=max_runtime_seconds)
    recovered: list[tuple[str, int, str]] = []
    task_specs = (
        (
            AnalysisTask,
            "analysis",
            "ANALYSIS_TASK_INTERRUPTED",
            "分析任务超过最长运行时间，可能因后端重启或请求中断而停止，请重新运行",
        ),
        (
            LyricsTask,
            "lyrics",
            "LYRICS_TASK_INTERRUPTED",
            "作词任务超过最长运行时间，可能因后端重启或请求中断而停止，请重新生成",
        ),
    )

    for model, task_type, error_code, error_message in task_specs:
        tasks = db.scalars(
            select(model).where(
                model.status.in_(
                    (TaskStatus.PENDING.value, TaskStatus.RUNNING.value)
                ),
                func.coalesce(model.started_at, model.created_at) < cutoff,
            )
        ).all()
        for task in tasks:
            task.status = TaskStatus.FAILED.value
            task.error_code = error_code
            task.error_message = error_message
            task.error_detail = {
                "reason": "task_runtime_exceeded",
                "max_runtime_seconds": round(max_runtime_seconds),
            }
            task.completed_at = now
            recovered.append((task_type, task.id, error_code))

    if not recovered:
        return 0

    db.commit()
    for task_type, task_id, error_code in recovered:
        task_logger.warning(
            "stale_text_task_recovered",
            extra={
                "task_id": str(task_id),
                "task_type": task_type,
                "error_code": error_code,
                "max_runtime_seconds": round(max_runtime_seconds),
            },
        )
    return len(recovered)


def _text_task_max_runtime_seconds(db: Session) -> float:
    active_config = db.scalar(
        select(AiProviderConfig)
        .where(AiProviderConfig.is_active.is_(True))
        .limit(1)
    )
    if active_config is None:
        timeout_seconds = settings.AI_REQUEST_TIMEOUT_SECONDS
        attempts = settings.AI_MAX_RETRIES
    else:
        timeout_seconds = active_config.request_timeout_seconds
        attempts = active_config.max_retries

    timeout_seconds = max(1.0, float(timeout_seconds))
    attempts = max(1, int(attempts))
    retry_delay_seconds = sum(
        min(2.0, 0.5 * (2 ** max(0, attempt - 1)))
        for attempt in range(1, attempts)
    )
    return (
        timeout_seconds * attempts
        + retry_delay_seconds
        + TEXT_TASK_GRACE_SECONDS
    )


def recover_stale_music_tasks(db: Session) -> int:
    now = utc_now()
    max_runtime_seconds = max(
        60.0,
        float(settings.SUNO_GENERATION_TIMEOUT_SECONDS) + 60.0,
    )
    cutoff = now - timedelta(seconds=max_runtime_seconds)
    tasks = db.scalars(
        select(MusicTask).where(
            MusicTask.status.in_(
                (TaskStatus.PENDING.value, TaskStatus.RUNNING.value)
            ),
            func.coalesce(MusicTask.started_at, MusicTask.created_at) < cutoff,
        )
    ).all()
    for task in tasks:
        task.status = TaskStatus.FAILED.value
        task.error_code = "MUSIC_TASK_INTERRUPTED"
        task.error_message = (
            "音乐任务超过最长运行时间，可能因后端重启或 Suno 请求中断而停止，请重新运行"
        )
        task.error_detail = {
            "reason": "task_runtime_exceeded",
            "max_runtime_seconds": round(max_runtime_seconds),
        }
        task.completed_at = now
    if not tasks:
        return 0
    db.commit()
    for task in tasks:
        task_logger.warning(
            "stale_music_task_recovered",
            extra={
                "task_id": str(task.id),
                "task_type": "music",
                "error_code": "MUSIC_TASK_INTERRUPTED",
                "max_runtime_seconds": round(max_runtime_seconds),
            },
        )
    return len(tasks)
