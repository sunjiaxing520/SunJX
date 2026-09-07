import hashlib
import hmac
import logging
import re
import secrets
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import Connection, Engine, delete, func, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.adapters.music_generation import (
    MusicGenerationInput,
    MusicGenerationOutput,
    MusicProviderError,
    MusicProviderPending,
    get_music_provider,
)
from app.core.config import music_execution_timeout_seconds, settings
from app.core.credential_crypto import (
    CredentialDecryptionError,
    credential_hint,
    decrypt_credential,
    encrypt_credential,
)
from app.core.database import SessionLocal
from app.core.exceptions import AppException
from app.core.logging import LOGGER_NAME
from app.core.time import utc_now
from app.models import (
    LyricsVersion,
    FavoriteItem,
    MusicProviderQuotaSnapshot,
    MusicProviderSettings,
    MusicResult,
    MusicTask,
    RankingEntry,
    RankingSnapshot,
    TaskStatus,
    User,
    UserRole,
)
from app.schemas.music import (
    MusicCreateRequest,
    MusicAdaptRequest,
    MusicExtendRequest,
    MusicProviderSettingsResponse,
    MusicProviderSettingsUpdate,
    MusicReferenceSongListResponse,
    MusicReferenceSongResponse,
    MusicResultListResponse,
    MusicResultResponse,
    MusicTaskDeleteResponse,
    MusicTaskListResponse,
    MusicTaskResponse,
    SunoApiOrgCallbackRequest,
    SunoApiOrgCallbackResponse,
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
    task = result.task
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
        task_operation=task.operation,
        task_model=task.model,
        style_tags=list(task.style_tags),
        negative_tags=list(task.negative_tags),
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
        style_tags=list(task.style_tags),
        instrumental=task.instrumental,
        negative_tags=task.negative_tags,
        requirements=task.requirements,
        adaptation_mode=task.adaptation_mode,
        source_title=task.source_title,
        source_artist=task.source_artist,
        source_url=task.source_url,
        rights_confirmed=task.rights_confirmed,
        rights_note=task.rights_note,
        external_task_id=task.external_task_id,
        provider_submitted_at=task.provider_submitted_at,
        provider_callback_type=task.provider_callback_type,
        provider_callback_received_at=task.provider_callback_received_at,
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
        provider_implementation=_selected_provider_implementation(db),
        model=_selected_music_model(db),
        requested_by_id=requested_by_id,
        lyrics_version_id=lyrics_version.id,
        title=(payload.title or lyrics_version.title).strip(),
        lyrics="" if payload.instrumental else lyrics_version.content,
        style_prompt=(payload.style_prompt or lyrics_version.style_prompt).strip(),
        style_tags=list(payload.style_tags),
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
        provider_implementation=_selected_provider_implementation(db),
        model=_selected_music_model(db),
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
        style_tags=list(source_task.style_tags),
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


def create_adaptation_task(
    db: Session,
    result_id: int,
    payload: MusicAdaptRequest,
    requested_by_id: int,
) -> MusicTaskResponse:
    source = _get_result(db, result_id)
    source_task = _get_task_model(db, source.task_id)
    _consume_music_task_quota(db, requested_by_id)
    task = MusicTask(
        status=TaskStatus.PENDING.value,
        operation="adapt",
        provider="suno",
        provider_implementation=_selected_provider_implementation(db),
        model=_selected_music_model(db),
        requested_by_id=requested_by_id,
        lyrics_version_id=source_task.lyrics_version_id,
        source_result_id=source.id,
        title=(payload.title or f"{source.title} · 授权改编").strip(),
        lyrics=(payload.lyrics if payload.lyrics is not None else source_task.lyrics),
        style_prompt=(
            payload.style_prompt
            if payload.style_prompt is not None
            else source_task.style_prompt
        ).strip(),
        style_tags=(list(payload.style_tags) or list(source_task.style_tags)),
        instrumental=source_task.instrumental,
        negative_tags=(list(payload.negative_tags) or list(source_task.negative_tags)),
        requirements=_clean_optional_text(
            payload.requirements
            if payload.requirements is not None
            else source_task.requirements
        ),
        adaptation_mode=payload.adaptation_mode,
        source_title=source.title,
        source_artist=_clean_optional_text(payload.source_artist),
        source_url=_clean_optional_text(payload.source_url),
        rights_confirmed=True,
        rights_note=_clean_optional_text(payload.rights_note),
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
    if (
        task.provider_implementation == "sunoapi_org"
        and task.external_task_id
    ):
        task.provider_submitted_at = utc_now()
    db.commit()
    return dispatch_music_task(db, task.id)


def regenerate_music_task(
    db: Session,
    task_id: int,
    requested_by_id: int,
) -> MusicTaskResponse:
    source = _get_task_model(db, task_id)
    if source.status != TaskStatus.COMPLETED.value:
        raise AppException(
            code="MUSIC_TASK_REGENERATE_CONFLICT",
            message="只有已完成的音乐任务可以再次生成",
            status_code=409,
        )
    _consume_music_task_quota(db, requested_by_id)
    task = MusicTask(
        status=TaskStatus.PENDING.value,
        operation=source.operation,
        provider="suno",
        provider_implementation=_selected_provider_implementation(db),
        model=_selected_music_model(db),
        requested_by_id=requested_by_id,
        lyrics_version_id=source.lyrics_version_id,
        source_result_id=source.source_result_id,
        title=source.title,
        lyrics=source.lyrics,
        style_prompt=source.style_prompt,
        style_tags=list(source.style_tags),
        instrumental=source.instrumental,
        negative_tags=list(source.negative_tags),
        requirements=source.requirements,
        adaptation_mode=source.adaptation_mode,
        source_title=source.source_title,
        source_artist=source.source_artist,
        source_url=source.source_url,
        rights_confirmed=source.rights_confirmed,
        rights_note=source.rights_note,
        max_attempts=max(1, settings.MUSIC_MAX_RETRIES),
        provider_status="created",
    )
    db.add(task)
    db.commit()
    return get_music_task(db, task.id)


def resume_after_human_verification(
    db: Session,
    task_id: int,
) -> MusicTaskResponse:
    task = _get_task_model(db, task_id)
    if not (
        task.status == TaskStatus.FAILED.value
        and (
            task.provider_status == "waiting_human_verification"
            or task.error_code == "SUNO_HUMAN_VERIFICATION_REQUIRED"
        )
    ):
        raise AppException(
            code="MUSIC_TASK_HUMAN_VERIFICATION_CONFLICT",
            message="只有等待人机验证的失败任务可以在管理员验证后恢复",
            status_code=409,
            detail={
                "task_status": task.status,
                "provider_status": task.provider_status,
                "error_code": task.error_code,
            },
        )

    task.status = TaskStatus.PENDING.value
    task.provider_status = "human_verification_completed"
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
    is_sunoapi_status_check = bool(
        task.provider_implementation == "sunoapi_org" and task.external_task_id
    )
    task.status = TaskStatus.RUNNING.value
    task.started_at = utc_now()
    if not is_sunoapi_status_check:
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
        provider = _music_provider_for_task(db, task)
        task.model = provider.model or task.model
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
            style_tags=list(task.style_tags),
            source_external_id=source_external_id,
        )
        if task.external_task_id:
            output = provider.resume(provider_payload, task.external_task_id)
        else:
            output = (
                provider.extend(provider_payload)
                if task.operation == "extend"
                or (task.operation == "adapt" and task.adaptation_mode == "extend")
                else provider.generate(provider_payload)
            )
        _complete_music_task(db, task, output)
        _refresh_music_quota_if_due(db, task.provider_implementation)
        return MusicTaskExecutionOutcome(status="completed")
    except MusicProviderPending as pending:
        return _handle_music_task_pending(db, task, pending)
    except MusicProviderError as exc:
        if is_sunoapi_status_check:
            task.attempt_count += 1
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
        .options(selectinload(MusicResult.task))
        .order_by(MusicResult.created_at.desc(), MusicResult.id.desc())
        .limit(limit)
    ).all()
    total = db.scalar(select(func.count(MusicResult.id))) or 0
    return MusicResultListResponse(
        items=[music_result_response(result) for result in results],
        total=total,
    )


def list_music_reference_songs(
    db: Session,
    query: str | None,
    limit: int = 20,
) -> MusicReferenceSongListResponse:
    statement = (
        select(RankingEntry, RankingSnapshot)
        .join(RankingSnapshot, RankingSnapshot.id == RankingEntry.snapshot_id)
        .order_by(
            RankingSnapshot.collected_at.desc(),
            RankingEntry.id.desc(),
        )
    )
    cleaned_query = (query or "").strip()
    if cleaned_query:
        pattern = f"%{cleaned_query}%"
        statement = statement.where(
            RankingEntry.title.ilike(pattern) | RankingEntry.artist.ilike(pattern)
        )

    candidates = db.execute(statement.limit(max(limit * 8, 80))).all()
    items: list[MusicReferenceSongResponse] = []
    seen: set[str] = set()
    for entry, snapshot in candidates:
        identity = entry.source_song_id or f"{entry.title}\n{entry.artist}"
        if identity in seen:
            continue
        seen.add(identity)
        items.append(
            MusicReferenceSongResponse(
                entry_id=entry.id,
                source_song_id=entry.source_song_id,
                title=entry.title,
                artist=entry.artist,
                cover_url=entry.cover_url,
                source_url=entry.source_url,
                duration_seconds=entry.duration_seconds,
                chart_name=snapshot.chart_name,
                snapshot_date=snapshot.snapshot_date,
                rank=entry.rank,
            )
        )
        if len(items) >= limit:
            break
    return MusicReferenceSongListResponse(items=items, total=len(items))


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
        result_ids = [result.id for result in task.results]
        if result_ids:
            db.execute(
                delete(FavoriteItem).where(
                    FavoriteItem.item_type == "music",
                    FavoriteItem.target_id.in_(result_ids),
                )
            )
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
    db.execute(
        delete(FavoriteItem).where(
            FavoriteItem.item_type == "music",
            FavoriteItem.target_id == result.id,
        )
    )
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


def _handle_music_task_pending(
    db: Session,
    task: MusicTask,
    pending: MusicProviderPending,
) -> MusicTaskExecutionOutcome:
    if pending.submitted_now and pending.call is not None:
        record_api_usage(
            db,
            task_type="music",
            task_id=task.id,
            operation=(
                f"music-{task.operation}-submit"
                if pending.submitted_now
                else f"music-{task.operation}-status"
            ),
            provider="suno",
            model=task.model,
            call=pending.call,
            status="completed",
        )
    db.refresh(task)
    if (
        task.provider_callback_type == "error"
        and task.status == TaskStatus.FAILED.value
    ):
        db.commit()
        return MusicTaskExecutionOutcome(status="failed")
    submitted_at = task.provider_submitted_at or task.created_at
    if submitted_at.tzinfo is None:
        submitted_at = submitted_at.replace(tzinfo=utc_now().tzinfo)
    elapsed = (utc_now() - submitted_at).total_seconds()
    if elapsed >= max(60.0, settings.SUNO_GENERATION_TIMEOUT_SECONDS):
        return _handle_music_task_error(
            db,
            task,
            MusicProviderError(
                "等待 SunoAPI 生成结果超时；外部任务编号已保留，可手动重试查询",
                code="SUNO_GENERATION_TIMEOUT",
                detail={"external_task_id": pending.external_task_id},
            ),
        )

    delay_seconds = max(5.0, pending.retry_after_seconds or 30.0)
    if task.provider_callback_type == "complete":
        delay_seconds = 0.0
    task.status = TaskStatus.PENDING.value
    task.provider_status = (
        f"callback_{task.provider_callback_type}"
        if task.provider_callback_type
        else pending.provider_status
    )
    task.external_task_id = pending.external_task_id
    task.next_attempt_at = utc_now() + timedelta(seconds=delay_seconds)
    task.completed_at = None
    task.error_code = None
    task.error_message = None
    task.error_detail = None
    db.commit()
    return MusicTaskExecutionOutcome(
        status="waiting_provider",
        retry_delay_seconds=delay_seconds,
    )


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
    task.provider_submitted_at = task.provider_submitted_at or utc_now()
    task.provider_status = "submitted"
    db.commit()


def _music_provider_for_task(db: Session, task: MusicTask):
    return _music_provider_for_implementation(
        db,
        task.provider_implementation,
        model=task.model,
        task_id=task.id,
        on_submitted=lambda external_task_id: _persist_external_task_id(
            db,
            task,
            external_task_id,
        ),
    )


def handle_sunoapi_org_callback(
    db: Session,
    task_id: int,
    signature: str,
    payload: SunoApiOrgCallbackRequest,
) -> tuple[SunoApiOrgCallbackResponse, bool]:
    settings_row = _get_or_create_music_settings(db)
    try:
        expected_signature = _sunoapi_org_callback_signature(settings_row, task_id)
    except MusicProviderError as exc:
        raise AppException(
            code=exc.code,
            message=str(exc),
            status_code=503,
        ) from exc
    if not hmac.compare_digest(signature, expected_signature):
        raise AppException(
            code="SUNOAPI_CALLBACK_UNAUTHORIZED",
            message="SunoAPI 回调签名无效",
            status_code=401,
        )

    task = db.scalar(
        select(MusicTask).where(MusicTask.id == task_id).with_for_update()
    )
    if task is None:
        raise AppException(
            code="SUNOAPI_CALLBACK_TASK_NOT_FOUND",
            message="SunoAPI 回调对应的音乐任务不存在",
            status_code=404,
        )
    if task.provider_implementation != "sunoapi_org":
        raise AppException(
            code="SUNOAPI_CALLBACK_PROVIDER_CONFLICT",
            message="该音乐任务不是由 SunoAPI 创建",
            status_code=409,
        )

    external_task_id = payload.data.task_id.strip()
    if task.external_task_id and task.external_task_id != external_task_id:
        raise AppException(
            code="SUNOAPI_CALLBACK_TASK_CONFLICT",
            message="SunoAPI 回调任务编号与本地记录不一致",
            status_code=409,
            detail={"task_id": task.id},
        )
    task.external_task_id = external_task_id
    task.provider_submitted_at = task.provider_submitted_at or utc_now()

    callback_type = payload.data.callback_type
    if task.status == TaskStatus.COMPLETED.value:
        db.commit()
        return (
            SunoApiOrgCallbackResponse(
                task_id=task.id,
                callback_type=callback_type,
            ),
            False,
        )

    stage_order = {"text": 1, "first": 2, "complete": 3, "error": 3}
    current_stage = task.provider_callback_type
    if current_stage == "complete" and callback_type != "complete":
        db.commit()
        return (
            SunoApiOrgCallbackResponse(
                task_id=task.id,
                callback_type=callback_type,
            ),
            False,
        )
    is_stale_stage = bool(
        current_stage
        and stage_order.get(current_stage, 0) > stage_order[callback_type]
    )
    if is_stale_stage:
        db.commit()
        return (
            SunoApiOrgCallbackResponse(
                task_id=task.id,
                callback_type=callback_type,
            ),
            False,
        )
    if not is_stale_stage:
        task.provider_callback_type = callback_type
        task.provider_callback_received_at = utc_now()

    should_dispatch = False
    if callback_type == "error" or payload.code != 200:
        if task.status != TaskStatus.COMPLETED.value:
            task.status = TaskStatus.FAILED.value
            task.provider_status = "callback_error"
            task.error_code = "SUNOAPI_CALLBACK_ERROR"
            task.error_message = payload.msg[:1000] or "SunoAPI 回调报告任务失败"
            task.error_detail = {
                "provider_code": payload.code,
                "external_task_id": external_task_id,
            }
            task.next_attempt_at = None
            task.completed_at = utc_now()
    elif callback_type == "complete":
        if task.status != TaskStatus.COMPLETED.value:
            task.status = TaskStatus.PENDING.value
            task.provider_status = "callback_complete"
            task.error_code = None
            task.error_message = None
            task.error_detail = None
            task.next_attempt_at = utc_now()
            task.completed_at = None
            should_dispatch = True
    elif task.status in {TaskStatus.PENDING.value, TaskStatus.RUNNING.value}:
        task.provider_status = f"callback_{callback_type}"

    db.commit()
    return (
        SunoApiOrgCallbackResponse(
            task_id=task.id,
            callback_type=callback_type,
        ),
        should_dispatch,
    )


def wake_music_task_from_callback(
    task_id: int,
    bind: Engine | Connection | None = None,
) -> None:
    if settings.MUSIC_QUEUE_MODE == "redis":
        try:
            get_music_queue().enqueue(task_id)
        except MusicQueueError:
            task_logger.exception(
                "sunoapi_callback_enqueue_failed",
                extra={
                    "task_id": str(task_id),
                    "task_type": "music",
                    "error_code": "MUSIC_QUEUE_UNAVAILABLE",
                },
            )
        return
    if settings.MUSIC_QUEUE_MODE == "inline":
        while True:
            outcome = execute_music_task(task_id, bind)
            if outcome.retry_delay_seconds is None:
                return
            time.sleep(max(0.0, outcome.retry_delay_seconds))


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
    selected = implementation or _selected_provider_implementation(db)
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


def music_provider_settings_response(
    settings_row: MusicProviderSettings,
    *,
    include_secret_details: bool = False,
) -> MusicProviderSettingsResponse:
    implementation = _effective_provider_implementation(settings_row)
    try:
        token = _sunoapi_org_token(settings_row)
    except MusicProviderError:
        token = ""
    callback_base_url = _sunoapi_org_callback_base_url(settings_row)
    return MusicProviderSettingsResponse(
        active_implementation=implementation,
        active_model=settings_row.active_model,
        sunoapi_org_token_configured=bool(token),
        sunoapi_org_token_hint=(
            settings_row.sunoapi_org_token_hint
            or (credential_hint(token) if token else None)
            if include_secret_details
            else None
        ),
        sunoapi_org_callback_base_url=(
            callback_base_url if include_secret_details else None
        ),
        sunoapi_org_callback_ready=bool(callback_base_url),
        updated_by_id=settings_row.updated_by_id,
        updated_at=settings_row.updated_at,
    )


def get_music_provider_settings(
    db: Session,
    *,
    include_secret_details: bool = False,
) -> MusicProviderSettingsResponse:
    return music_provider_settings_response(
        _get_or_create_music_settings(db),
        include_secret_details=include_secret_details,
    )


def update_music_provider_settings(
    db: Session,
    payload: MusicProviderSettingsUpdate,
    user_id: int,
) -> MusicProviderSettingsResponse:
    settings_row = _get_or_create_music_settings(db)
    changes = payload.model_dump(exclude_unset=True)
    if payload.active_model is not None:
        settings_row.active_model = payload.active_model
    if payload.active_implementation is not None:
        settings_row.active_implementation = payload.active_implementation
    if "sunoapi_org_callback_base_url" in changes:
        settings_row.sunoapi_org_callback_base_url = (
            _validate_sunoapi_org_callback_base_url(
                payload.sunoapi_org_callback_base_url
            )
        )
    if payload.clear_sunoapi_org_token:
        settings_row.sunoapi_org_token_encrypted = None
        settings_row.sunoapi_org_token_hint = None
    elif payload.sunoapi_org_token is not None:
        token = payload.sunoapi_org_token.get_secret_value().strip()
        if not token:
            raise AppException(
                code="SUNOAPI_TOKEN_INVALID",
                message="SunoAPI Token 不能为空",
                status_code=422,
            )
        settings_row.sunoapi_org_token_encrypted = encrypt_credential(token)
        settings_row.sunoapi_org_token_hint = credential_hint(token)

    if _effective_provider_implementation(settings_row) == "sunoapi_org":
        missing: list[str] = []
        try:
            configured_token = _sunoapi_org_token(settings_row)
        except MusicProviderError as exc:
            raise AppException(
                code=exc.code,
                message=str(exc),
                status_code=422,
            ) from exc
        if not configured_token:
            missing.append("Token")
        if not _sunoapi_org_callback_base_url(settings_row):
            missing.append("回调公网地址")
        normalized_model = re.sub(
            r"[^a-z0-9]+", "", settings_row.active_model.lower()
        )
        if normalized_model not in {
            "v4",
            "v45",
            "v45plus",
            "v45all",
            "v5",
            "v55",
        }:
            raise AppException(
                code="SUNOAPI_MODEL_INVALID",
                message=f"SunoAPI 不支持模型 {settings_row.active_model}",
                status_code=422,
            )
        if missing:
            raise AppException(
                code="SUNOAPI_CONFIGURATION_INCOMPLETE",
                message=f"启用 SunoAPI 前请配置：{'、'.join(missing)}",
                status_code=422,
                detail={"missing": missing},
            )
    settings_row.updated_by_id = user_id
    db.commit()
    db.refresh(settings_row)
    return music_provider_settings_response(
        settings_row,
        include_secret_details=True,
    )


def refresh_music_quota(
    db: Session,
    implementation: str | None = None,
) -> SunoQuotaResponse:
    selected = implementation or _selected_provider_implementation(db)
    try:
        provider = _music_provider_for_implementation(db, selected)
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


def _selected_provider_implementation(db: Session) -> str:
    return _effective_provider_implementation(_get_or_create_music_settings(db))


def _effective_provider_implementation(
    settings_row: MusicProviderSettings,
) -> str:
    value = (
        settings_row.active_implementation
        or settings.SUNO_PROVIDER_IMPLEMENTATION
    ).strip().lower()
    aliases = {
        "compat": "compatibility",
        "sunoapi": "sunoapi_org",
        "sunoapi.org": "sunoapi_org",
    }
    selected = aliases.get(value, value)
    if selected not in {"official", "sunoapi_org", "compatibility"}:
        raise AppException(
            code="SUNO_PROVIDER_IMPLEMENTATION_INVALID",
            message=f"不支持的 Suno Provider 实现：{value}",
            status_code=503,
            detail={
                "allowed": ["official", "sunoapi_org", "compatibility"]
            },
        )
    return selected


def _selected_music_model(db: Session) -> str:
    return _get_or_create_music_settings(db).active_model


def _get_or_create_music_settings(db: Session) -> MusicProviderSettings:
    settings_row = db.get(MusicProviderSettings, 1)
    if settings_row is None:
        settings_row = MusicProviderSettings(
            id=1,
            active_model=(settings.SUNO_MODEL or "v4.5").strip() or "v4.5",
        )
        db.add(settings_row)
        db.flush()
    if not settings_row.sunoapi_org_callback_secret_encrypted:
        settings_row.sunoapi_org_callback_secret_encrypted = encrypt_credential(
            secrets.token_urlsafe(32)
        )
    if settings_row in db.new or db.is_modified(settings_row):
        db.commit()
        db.refresh(settings_row)
    return settings_row


def _music_provider_for_implementation(
    db: Session,
    implementation: str,
    *,
    model: str | None = None,
    task_id: int | None = None,
    on_submitted=None,
):
    if implementation != "sunoapi_org":
        return get_music_provider(
            implementation,
            model=model,
            on_submitted=on_submitted,
        )
    settings_row = _get_or_create_music_settings(db)
    callback_url = None
    if task_id is not None:
        callback_url = _sunoapi_org_callback_url(settings_row, task_id)
    return get_music_provider(
        implementation,
        model=model or settings_row.active_model,
        on_submitted=on_submitted,
        api_key=_sunoapi_org_token(settings_row),
        base_url=settings.SUNOAPI_ORG_BASE_URL,
        callback_url=callback_url,
    )


def _sunoapi_org_token(settings_row: MusicProviderSettings) -> str:
    if settings_row.sunoapi_org_token_encrypted:
        try:
            return decrypt_credential(settings_row.sunoapi_org_token_encrypted)
        except CredentialDecryptionError as exc:
            raise MusicProviderError(
                "SunoAPI Token 无法解密，请管理员重新填写 Token",
                code="SUNOAPI_CREDENTIAL_DECRYPTION_FAILED",
            ) from exc
    return settings.SUNOAPI_ORG_API_KEY.strip()


def _sunoapi_org_callback_base_url(
    settings_row: MusicProviderSettings,
) -> str:
    return (
        settings_row.sunoapi_org_callback_base_url
        or settings.SUNOAPI_ORG_CALLBACK_BASE_URL
    ).strip().rstrip("/")


def _sunoapi_org_callback_url(
    settings_row: MusicProviderSettings,
    task_id: int,
) -> str:
    base_url = _sunoapi_org_callback_base_url(settings_row)
    if not base_url:
        raise MusicProviderError(
            "尚未配置 SunoAPI 回调公网地址",
            code="SUNOAPI_CALLBACK_NOT_CONFIGURED",
        )
    signature = _sunoapi_org_callback_signature(settings_row, task_id)
    return (
        f"{base_url}{settings.API_V1_PREFIX}/music/callbacks/"
        f"sunoapi-org/{task_id}/{signature}"
    )


def _sunoapi_org_callback_signature(
    settings_row: MusicProviderSettings,
    task_id: int,
) -> str:
    encrypted = settings_row.sunoapi_org_callback_secret_encrypted
    if not encrypted:
        raise MusicProviderError(
            "SunoAPI 回调密钥尚未初始化",
            code="SUNOAPI_CALLBACK_SECRET_MISSING",
        )
    try:
        secret = decrypt_credential(encrypted)
    except CredentialDecryptionError as exc:
        raise MusicProviderError(
            "SunoAPI 回调密钥无法解密，请检查加密配置",
            code="SUNOAPI_CALLBACK_SECRET_INVALID",
        ) from exc
    return hmac.new(
        secret.encode("utf-8"),
        f"sunoapi-org:{task_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _validate_sunoapi_org_callback_base_url(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise AppException(
            code="SUNOAPI_CALLBACK_URL_INVALID",
            message="SunoAPI 回调公网地址必须是完整的 HTTPS 地址",
            status_code=422,
        )
    return value.rstrip("/")


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
