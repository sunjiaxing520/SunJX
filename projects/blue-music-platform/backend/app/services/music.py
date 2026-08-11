import logging
import re
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from sqlalchemy import Connection, Engine, func, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.adapters.music_generation import (
    MusicGenerationInput,
    MusicGenerationOutput,
    MusicProviderError,
    get_music_provider,
)
from app.core.config import music_execution_timeout_seconds, settings
from app.core.database import SessionLocal
from app.core.exceptions import AppException
from app.core.logging import LOGGER_NAME
from app.core.time import utc_now
from app.models import (
    LyricsVersion,
    MusicProviderQuotaSnapshot,
    MusicResult,
    MusicTask,
    TaskStatus,
    User,
    UserRole,
)
from app.schemas.music import (
    MusicCreateRequest,
    MusicExtendRequest,
    MusicResultListResponse,
    MusicResultResponse,
    MusicTaskDeleteResponse,
    MusicTaskListResponse,
    MusicTaskResponse,
    SunoQuotaResponse,
)
from app.services.api_usage import record_api_usage, task_api_usage
from app.services.music_queue import MusicQueueError, get_music_queue
from app.services.music_storage import (
    MusicStorageError,
    StoredMusicObject,
    get_music_object_store,
)
from app.services.task_recovery import recover_stale_music_tasks


task_logger = logging.getLogger(f"{LOGGER_NAME}.tasks")


@dataclass(frozen=True)
class MusicTaskExecutionOutcome:
    status: str
    retry_delay_seconds: float | None = None


def music_result_response(result: MusicResult) -> MusicResultResponse:
    return MusicResultResponse(
        id=result.id,
        task_id=result.task_id,
        external_id=result.external_id,
        title=result.title,
        media_type=result.media_type,
        duration_seconds=result.duration_seconds,
        image_url=result.image_url,
        provider_page_url=result.provider_page_url,
        storage_backend=result.storage_backend,
        storage_error=result.storage_error,
        audio_ready=bool(result.storage_key or result.audio_url),
        audio_path=f"/music/results/{result.id}/audio",
        download_path=f"/music/results/{result.id}/download",
        created_at=result.created_at,
    )


def music_task_response(db: Session, task: MusicTask) -> MusicTaskResponse:
    return MusicTaskResponse(
        id=task.id,
        status=task.status,
        operation=task.operation,
        provider=task.provider,
        provider_implementation=task.provider_implementation,
        model=task.model,
        lyrics_version_id=task.lyrics_version_id,
        source_result_id=task.source_result_id,
        title=task.title,
        lyrics=task.lyrics,
        style_prompt=task.style_prompt,
        instrumental=task.instrumental,
        negative_tags=task.negative_tags,
        requirements=task.requirements,
        external_task_id=task.external_task_id,
        provider_status=task.provider_status,
        error_code=task.error_code,
        error_message=task.error_message,
        attempt_count=task.attempt_count,
        max_attempts=task.max_attempts,
        next_attempt_at=task.next_attempt_at,
        last_queued_at=task.last_queued_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        created_at=task.created_at,
        api_usage=task_api_usage(db, "music", task.id),
        results=[music_result_response(result) for result in task.results],
    )


def create_music_task(
    db: Session,
    payload: MusicCreateRequest,
    requested_by_id: int,
) -> MusicTaskResponse:
    lyrics_version = db.get(LyricsVersion, payload.lyrics_version_id)
    if lyrics_version is None:
        raise AppException(
            code="LYRICS_VERSION_NOT_FOUND",
            message="歌词版本不存在",
            status_code=404,
        )

    _consume_music_task_quota(db, requested_by_id)

    task = MusicTask(
        status=TaskStatus.PENDING.value,
        operation="generate",
        provider="suno",
        provider_implementation=_selected_provider_implementation(),
        model=settings.SUNO_MODEL or None,
        requested_by_id=requested_by_id,
        lyrics_version_id=lyrics_version.id,
        title=(payload.title or lyrics_version.title).strip(),
        lyrics="" if payload.instrumental else lyrics_version.content,
        style_prompt=(payload.style_prompt or lyrics_version.style_prompt).strip(),
        instrumental=payload.instrumental,
        negative_tags=payload.negative_tags,
        requirements=_clean_optional_text(payload.requirements),
        max_attempts=max(1, settings.MUSIC_MAX_RETRIES),
        provider_status="created",
    )
    db.add(task)
    db.commit()
    return get_music_task(db, task.id)


def create_extension_task(
    db: Session,
    result_id: int,
    payload: MusicExtendRequest,
    requested_by_id: int,
) -> MusicTaskResponse:
    source = _get_result(db, result_id)
    source_task = _get_task_model(db, source.task_id)
    _consume_music_task_quota(db, requested_by_id)
    task = MusicTask(
        status=TaskStatus.PENDING.value,
        operation="extend",
        provider="suno",
        provider_implementation=_selected_provider_implementation(),
        model=source_task.model or settings.SUNO_MODEL or None,
        requested_by_id=requested_by_id,
        lyrics_version_id=source_task.lyrics_version_id,
        source_result_id=source.id,
        title=(payload.title or source.title).strip(),
        lyrics=(payload.lyrics if payload.lyrics is not None else source_task.lyrics),
        style_prompt=(
            payload.style_prompt
            if payload.style_prompt is not None
            else source_task.style_prompt
        ).strip(),
        instrumental=source_task.instrumental,
        negative_tags=list(source_task.negative_tags),
        requirements=_clean_optional_text(
            payload.requirements
            if payload.requirements is not None
            else source_task.requirements
        ),
        max_attempts=max(1, settings.MUSIC_MAX_RETRIES),
        provider_status="created",
    )
    db.add(task)
    db.commit()
    return get_music_task(db, task.id)


def dispatch_music_task(
    db: Session,
    task_id: int,
) -> MusicTaskResponse:
    task = _get_task_model(db, task_id)
    mode = settings.MUSIC_QUEUE_MODE
    if mode == "inline":
        while True:
            outcome = execute_music_task_in_session(db, task_id)
            if outcome.retry_delay_seconds is None:
                break
            time.sleep(max(0.0, outcome.retry_delay_seconds))
        db.expire_all()
        return get_music_task(db, task_id)
    if mode != "redis":
        return _mark_queue_failure(
            db,
            task,
            code="MUSIC_QUEUE_MODE_INVALID",
            message=f"不支持的音乐队列模式：{mode}",
        )

    try:
        get_music_queue().enqueue(task_id)
    except MusicQueueError as exc:
        return _mark_queue_failure(
            db,
            task,
            code="MUSIC_QUEUE_UNAVAILABLE",
            message=str(exc),
        )
    task.provider_status = "queued"
    task.last_queued_at = utc_now()
    db.commit()
    return get_music_task(db, task_id)


def retry_music_task(db: Session, task_id: int) -> MusicTaskResponse:
    task = _get_task_model(db, task_id)
    if task.status != TaskStatus.FAILED.value:
        raise AppException(
            code="MUSIC_TASK_RETRY_CONFLICT",
            message="只有失败的音乐任务可以重新入队",
            status_code=409,
        )
    task.status = TaskStatus.PENDING.value
    task.provider_status = "retry_requested"
    task.max_attempts = max(
        task.max_attempts,
        task.attempt_count + max(1, settings.MUSIC_MAX_RETRIES),
    )
    task.next_attempt_at = None
    task.completed_at = None
    task.error_code = None
    task.error_message = None
    task.error_detail = None
    db.commit()
    return dispatch_music_task(db, task.id)


def wait_for_music_task_completion(
    db: Session,
    task_id: int,
) -> MusicTaskResponse:
    task = get_music_task(db, task_id)
    max_attempts = max(1, task.max_attempts)
    retry_window_seconds = max(
        0.0,
        settings.MUSIC_RETRY_MAX_SECONDS * (max_attempts - 1),
    )
    deadline = time.monotonic() + max(
        60.0,
        (music_execution_timeout_seconds() * max_attempts)
        + retry_window_seconds,
    )
    while time.monotonic() < deadline:
        db.expire_all()
        task = get_music_task(db, task_id)
        if task.status not in (
            TaskStatus.PENDING.value,
            TaskStatus.RUNNING.value,
        ):
            return task
        time.sleep(min(2.0, max(0.5, settings.SUNO_POLL_INTERVAL_SECONDS)))
    raise AppException(
        code="WORKFLOW_MUSIC_WAIT_TIMEOUT",
        message="自动流程等待音乐任务结束超时，音乐任务仍会在后台继续运行",
        status_code=504,
        detail={"task_id": task_id},
    )


def execute_music_task(
    task_id: int,
    bind: Engine | Connection | None = None,
) -> MusicTaskExecutionOutcome:
    session_factory = (
        sessionmaker(bind=bind, autocommit=False, autoflush=False)
        if bind is not None
        else SessionLocal
    )
    with session_factory() as db:
        return execute_music_task_in_session(db, task_id)


def execute_music_task_in_session(
    db: Session,
    task_id: int,
) -> MusicTaskExecutionOutcome:
    task = _load_task(db, task_id)
    if task is None or task.status != TaskStatus.PENDING.value:
        return MusicTaskExecutionOutcome(status="ignored")
    task.status = TaskStatus.RUNNING.value
    task.started_at = utc_now()
    task.attempt_count += 1
    task.next_attempt_at = None
    task.provider_status = "running"
    task.error_code = None
    task.error_message = None
    task.error_detail = None
    db.commit()
    task_logger.info(
        "music_task_started",
        extra={"task_id": str(task.id), "task_type": "music"},
    )

    try:
        provider = get_music_provider(
            task.provider_implementation,
            on_submitted=lambda external_task_id: _persist_external_task_id(
                db,
                task,
                external_task_id,
            ),
        )
        task.model = provider.model
        source_external_id = None
        if task.source_result_id is not None:
            source = db.get(MusicResult, task.source_result_id)
            if source is None:
                raise MusicProviderError(
                    "用于续写的原始音乐结果已经不存在",
                    code="MUSIC_SOURCE_RESULT_NOT_FOUND",
                )
            source_external_id = source.external_id

        provider_payload = MusicGenerationInput(
            title=task.title,
            lyrics=task.lyrics,
            style_prompt=task.style_prompt,
            instrumental=task.instrumental,
            negative_tags=list(task.negative_tags),
            requirements=task.requirements,
            source_external_id=source_external_id,
        )
        if task.external_task_id:
            output = provider.resume(provider_payload, task.external_task_id)
        else:
            output = (
                provider.extend(provider_payload)
                if task.operation == "extend"
                else provider.generate(provider_payload)
            )
        _complete_music_task(db, task, output)
        _refresh_music_quota_if_due(db, task.provider_implementation)
        return MusicTaskExecutionOutcome(status="completed")
    except MusicProviderError as exc:
        return _handle_music_task_error(db, task, exc)
    except Exception:
        task_logger.exception(
            "music_task_failed",
            extra={
                "task_id": str(task.id),
                "task_type": "music",
                "error_code": "MUSIC_UNEXPECTED_ERROR",
            },
        )
        return _handle_music_task_error(
            db,
            task,
            MusicProviderError(
                "音乐生成发生未预期错误，请按任务编号检索日志",
                code="MUSIC_UNEXPECTED_ERROR",
                retryable=True,
            ),
        )


def get_music_task(db: Session, task_id: int) -> MusicTaskResponse:
    recover_stale_music_tasks(db)
    task = _load_task(db, task_id)
    if task is None:
        raise AppException(
            code="MUSIC_TASK_NOT_FOUND",
            message="音乐任务不存在",
            status_code=404,
        )
    return music_task_response(db, task)


def list_music_tasks(db: Session, limit: int = 15) -> MusicTaskListResponse:
    recover_stale_music_tasks(db)
    tasks = db.scalars(
        select(MusicTask)
        .options(selectinload(MusicTask.results))
        .order_by(MusicTask.created_at.desc(), MusicTask.id.desc())
        .limit(limit)
    ).all()
    total = db.scalar(select(func.count(MusicTask.id))) or 0
    return MusicTaskListResponse(
        items=[music_task_response(db, task) for task in tasks],
        total=total,
    )


def list_music_results(db: Session, limit: int = 30) -> MusicResultListResponse:
    results = db.scalars(
        select(MusicResult)
        .order_by(MusicResult.created_at.desc(), MusicResult.id.desc())
        .limit(limit)
    ).all()
    total = db.scalar(select(func.count(MusicResult.id))) or 0
    return MusicResultListResponse(
        items=[music_result_response(result) for result in results],
        total=total,
    )


def delete_music_task(db: Session, task_id: int) -> None:
    delete_music_tasks(db, [task_id])


def delete_music_tasks(
    db: Session,
    task_ids: list[int],
) -> MusicTaskDeleteResponse:
    ordered_ids = list(dict.fromkeys(task_ids))
    tasks = db.scalars(
        select(MusicTask)
        .options(selectinload(MusicTask.results))
        .where(MusicTask.id.in_(ordered_ids))
        .with_for_update()
    ).all()
    tasks_by_id = {task.id: task for task in tasks}
    missing_ids = [task_id for task_id in ordered_ids if task_id not in tasks_by_id]
    if missing_ids:
        raise AppException(
            code="MUSIC_TASK_NOT_FOUND",
            message="部分音乐任务不存在或已经被删除",
            status_code=404,
            detail={"missing_task_ids": missing_ids},
        )
    active_ids = [
        task.id
        for task in tasks
        if task.status in (TaskStatus.PENDING.value, TaskStatus.RUNNING.value)
    ]
    if active_ids:
        raise AppException(
            code="MUSIC_TASK_DELETE_CONFLICT",
            message="排队或运行中的音乐任务不能删除",
            status_code=409,
            detail={"active_task_ids": active_ids},
        )

    for task_id in ordered_ids:
        task = tasks_by_id[task_id]
        for result in task.results:
            _delete_storage_file(result.storage_key, result.storage_backend)
        db.delete(task)
    db.commit()
    return MusicTaskDeleteResponse(
        deleted_count=len(ordered_ids),
        deleted_task_ids=ordered_ids,
    )


def delete_music_result(db: Session, result_id: int) -> None:
    result = _get_result(db, result_id)
    active_extension = db.scalar(
        select(MusicTask.id).where(
            MusicTask.source_result_id == result.id,
            MusicTask.status.in_((TaskStatus.PENDING.value, TaskStatus.RUNNING.value)),
        )
    )
    if active_extension is not None:
        raise AppException(
            code="MUSIC_RESULT_DELETE_CONFLICT",
            message="该音乐正在被续写，暂时不能删除",
            status_code=409,
            detail={"active_task_id": active_extension},
        )
    _delete_storage_file(result.storage_key, result.storage_backend)
    db.delete(result)
    db.commit()


def get_music_result(db: Session, result_id: int) -> MusicResult:
    return _get_result(db, result_id)


def resolve_storage_path(
    storage_key: str | None,
    storage_backend: str = "local",
) -> Path | None:
    try:
        return get_music_object_store(storage_backend).resolve_local_path(storage_key)
    except MusicStorageError:
        return None


def create_storage_download_url(
    result: MusicResult,
    *,
    filename: str,
    attachment: bool,
) -> str | None:
    if not result.storage_key:
        return None
    try:
        return get_music_object_store(result.storage_backend).create_download_url(
            result.storage_key,
            filename=filename,
            media_type=result.media_type,
            attachment=attachment,
        )
    except MusicStorageError as exc:
        raise AppException(
            code="MUSIC_STORAGE_URL_FAILED",
            message="生成音乐临时访问地址失败，请检查对象存储配置",
            status_code=503,
            detail={"storage_backend": result.storage_backend},
        ) from exc


def _complete_music_task(
    db: Session,
    task: MusicTask,
    output: MusicGenerationOutput,
) -> None:
    if not output.tracks:
        raise MusicProviderError(
            "Suno 任务已结束，但没有返回可用音频",
            code="SUNO_NO_AUDIO_RESULT",
            call=output.call,
        )
    task.external_task_id = output.external_task_id
    task.provider_status = output.provider_status
    for track in output.tracks:
        result = MusicResult(
            task_id=task.id,
            external_id=track.external_id,
            title=(track.title or task.title)[:200],
            audio_url=track.audio_url,
            media_type=track.media_type or "audio/mpeg",
            duration_seconds=track.duration_seconds,
            image_url=track.image_url,
            provider_page_url=track.provider_page_url,
        )
        db.add(result)
        db.flush()
        try:
            stored = _archive_audio(
                task.id,
                result.id,
                track.audio_url,
                result.media_type,
            )
            result.storage_key = stored.key
            result.storage_backend = stored.backend
        except MusicStorageError as exc:
            result.storage_error = str(exc)[:500]

    record_api_usage(
        db,
        task_type="music",
        task_id=task.id,
        operation=f"music-{task.operation}",
        provider="suno",
        model=task.model,
        call=output.call,
        status="completed",
    )
    task.status = TaskStatus.COMPLETED.value
    task.next_attempt_at = None
    task.completed_at = utc_now()
    db.commit()
    task_logger.info(
        "music_task_completed",
        extra={"task_id": str(task.id), "task_type": "music"},
    )


def _handle_music_task_error(
    db: Session,
    task: MusicTask,
    error: MusicProviderError,
) -> MusicTaskExecutionOutcome:
    detail = dict(error.detail or {})
    external_task_id = detail.get("external_task_id")
    if external_task_id and not task.external_task_id:
        task.external_task_id = str(external_task_id)
    if error.call is not None:
        record_api_usage(
            db,
            task_type="music",
            task_id=task.id,
            operation=f"music-{task.operation}",
            provider="suno",
            model=task.model,
            call=error.call,
            status="failed",
            error_code=error.code,
            error_message=str(error),
        )
    task.error_code = error.code
    task.error_message = str(error)
    task.error_detail = detail or None

    if error.retryable and task.attempt_count < task.max_attempts:
        delay_seconds = _retry_delay_seconds(task, error)
        task.status = TaskStatus.PENDING.value
        task.provider_status = "retry_scheduled"
        task.next_attempt_at = utc_now() + timedelta(seconds=delay_seconds)
        task.completed_at = None
        db.commit()
        task_logger.warning(
            "music_task_retry_scheduled",
            extra={
                "task_id": str(task.id),
                "task_type": "music",
                "error_code": error.code,
                "attempt_count": task.attempt_count,
                "retry_delay_seconds": round(delay_seconds),
            },
        )
        return MusicTaskExecutionOutcome(
            status="retry_scheduled",
            retry_delay_seconds=delay_seconds,
        )

    task.status = TaskStatus.FAILED.value
    task.provider_status = (
        "waiting_human_verification"
        if error.requires_human
        else "failed"
    )
    task.next_attempt_at = None
    task.completed_at = utc_now()
    db.commit()
    task_logger.warning(
        "music_task_failed",
        extra={
            "task_id": str(task.id),
            "task_type": "music",
            "error_code": error.code,
        },
    )
    return MusicTaskExecutionOutcome(status="failed")


def _mark_queue_failure(
    db: Session,
    task: MusicTask,
    *,
    code: str,
    message: str,
) -> MusicTaskResponse:
    task.status = TaskStatus.FAILED.value
    task.provider_status = "queue_failed"
    task.error_code = code
    task.error_message = message
    task.error_detail = {"queue_mode": settings.MUSIC_QUEUE_MODE}
    task.completed_at = utc_now()
    db.commit()
    return get_music_task(db, task.id)


def _retry_delay_seconds(
    task: MusicTask,
    error: MusicProviderError,
) -> float:
    exponential = settings.MUSIC_RETRY_BASE_SECONDS * (
        2 ** max(0, task.attempt_count - 1)
    )
    suggested = error.retry_after_seconds or 0.0
    return max(
        0.0,
        min(
            settings.MUSIC_RETRY_MAX_SECONDS,
            max(exponential, suggested),
        ),
    )


def _load_task(db: Session, task_id: int) -> MusicTask | None:
    return db.scalar(
        select(MusicTask)
        .options(selectinload(MusicTask.results))
        .where(MusicTask.id == task_id)
    )


def _persist_external_task_id(
    db: Session,
    task: MusicTask,
    external_task_id: str,
) -> None:
    value = external_task_id.strip()
    if not value or len(value) > 200:
        raise MusicProviderError(
            "Suno 返回的外部任务编号无效，无法可靠保存",
            code="SUNO_EXTERNAL_TASK_INVALID",
        )
    if task.external_task_id and task.external_task_id != value:
        raise MusicProviderError(
            "Suno 返回了与当前任务不一致的外部任务编号",
            code="SUNO_EXTERNAL_TASK_CONFLICT",
            detail={
                "expected_external_task_id": task.external_task_id,
                "received_external_task_id": value,
            },
        )
    task.external_task_id = value
    task.provider_status = "submitted"
    db.commit()


def _get_task_model(db: Session, task_id: int) -> MusicTask:
    task = _load_task(db, task_id)
    if task is None:
        raise AppException(
            code="MUSIC_TASK_NOT_FOUND",
            message="音乐任务不存在",
            status_code=404,
        )
    return task


def _get_result(db: Session, result_id: int) -> MusicResult:
    result = db.get(MusicResult, result_id)
    if result is None:
        raise AppException(
            code="MUSIC_RESULT_NOT_FOUND",
            message="音乐结果不存在",
            status_code=404,
        )
    return result


def _archive_audio(
    task_id: int,
    result_id: int,
    url: str,
    media_type: str,
) -> StoredMusicObject:
    return get_music_object_store().archive(
        task_id=task_id,
        result_id=result_id,
        source_url=url,
        media_type=media_type,
    )


def _delete_storage_file(
    storage_key: str | None,
    storage_backend: str,
) -> None:
    try:
        get_music_object_store(storage_backend).delete(storage_key)
    except MusicStorageError as exc:
        raise AppException(
            code="MUSIC_STORAGE_DELETE_FAILED",
            message="删除音乐对象失败，数据库记录已保留",
            status_code=503,
            detail={"storage_backend": storage_backend},
        ) from exc


def latest_music_quota(
    db: Session,
    implementation: str | None = None,
) -> SunoQuotaResponse | None:
    selected = implementation or _selected_provider_implementation()
    snapshot = db.scalar(
        select(MusicProviderQuotaSnapshot)
        .where(
            MusicProviderQuotaSnapshot.provider_implementation == selected
        )
        .order_by(
            MusicProviderQuotaSnapshot.checked_at.desc(),
            MusicProviderQuotaSnapshot.id.desc(),
        )
        .limit(1)
    )
    return _quota_response(snapshot) if snapshot else None


def refresh_music_quota(
    db: Session,
    implementation: str | None = None,
) -> SunoQuotaResponse:
    selected = implementation or _selected_provider_implementation()
    try:
        provider = get_music_provider(selected)
        quota = provider.get_quota()
        snapshot = MusicProviderQuotaSnapshot(
            provider="suno",
            provider_implementation=provider.implementation,
            status="available",
            credits_remaining=quota.credits_remaining,
            usage=quota.usage,
            quota_limit=quota.limit,
            period=quota.period,
            raw_usage=quota.raw,
            checked_at=quota.call.completed_at,
        )
    except MusicProviderError as exc:
        snapshot = MusicProviderQuotaSnapshot(
            provider="suno",
            provider_implementation=selected,
            status="error",
            error_code=exc.code,
            error_message=str(exc),
            checked_at=utc_now(),
        )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return _quota_response(snapshot)


def _refresh_music_quota_if_due(
    db: Session,
    implementation: str,
) -> None:
    try:
        latest = db.scalar(
            select(MusicProviderQuotaSnapshot)
            .where(
                MusicProviderQuotaSnapshot.provider_implementation == implementation
            )
            .order_by(MusicProviderQuotaSnapshot.checked_at.desc())
            .limit(1)
        )
        if latest is not None:
            checked_at = latest.checked_at
            if checked_at.tzinfo is None:
                checked_at = checked_at.replace(tzinfo=utc_now().tzinfo)
            age = (utc_now() - checked_at).total_seconds()
            if age < max(0.0, settings.SUNO_QUOTA_REFRESH_INTERVAL_SECONDS):
                return
        refresh_music_quota(db, implementation)
    except Exception:
        db.rollback()
        task_logger.exception(
            "music_quota_refresh_failed",
            extra={
                "task_type": "music",
                "error_code": "SUNO_QUOTA_REFRESH_FAILED",
                "provider_implementation": implementation,
            },
        )


def _quota_response(
    snapshot: MusicProviderQuotaSnapshot,
) -> SunoQuotaResponse:
    return SunoQuotaResponse(
        status=snapshot.status,
        provider_implementation=snapshot.provider_implementation,
        credits_remaining=snapshot.credits_remaining,
        usage=snapshot.usage,
        quota_limit=snapshot.quota_limit,
        period=snapshot.period,
        error_code=snapshot.error_code,
        error_message=snapshot.error_message,
        checked_at=snapshot.checked_at,
    )


def _selected_provider_implementation() -> str:
    value = settings.SUNO_PROVIDER_IMPLEMENTATION.strip().lower()
    selected = "compatibility" if value == "compat" else value
    if selected not in {"official", "compatibility"}:
        raise AppException(
            code="SUNO_PROVIDER_IMPLEMENTATION_INVALID",
            message=f"不支持的 Suno Provider 实现：{value}",
            status_code=503,
            detail={"allowed": ["official", "compatibility"]},
        )
    return selected


def _consume_music_task_quota(db: Session, user_id: int) -> None:
    user = db.scalar(
        select(User).where(User.id == user_id).with_for_update()
    )
    if user is None:
        raise AppException(
            code="USER_NOT_FOUND",
            message="用户不存在",
            status_code=404,
        )
    if user.role == UserRole.SUPER_ADMIN:
        return
    if user.music_quota_remaining <= 0:
        raise AppException(
            code="MUSIC_TASK_QUOTA_EXHAUSTED",
            message="音乐任务额度已用完，请联系管理员分配额度",
            status_code=403,
            detail={"remaining_tasks": 0},
        )

    user.music_quota_remaining -= 1
    user.music_quota_used += 1


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None
