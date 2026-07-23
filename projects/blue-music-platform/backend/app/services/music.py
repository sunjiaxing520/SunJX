import logging
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy import Connection, Engine, func, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.adapters.music_generation import (
    MusicGenerationInput,
    MusicGenerationOutput,
    MusicProviderError,
    get_music_provider,
)
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import LOGGER_NAME
from app.core.time import utc_now
from app.models import LyricsVersion, MusicResult, MusicTask, TaskStatus
from app.schemas.music import (
    MusicCreateRequest,
    MusicExtendRequest,
    MusicResultListResponse,
    MusicResultResponse,
    MusicTaskDeleteResponse,
    MusicTaskListResponse,
    MusicTaskResponse,
)
from app.services.api_usage import record_api_usage, task_api_usage
from app.services.task_recovery import recover_stale_music_tasks


task_logger = logging.getLogger(f"{LOGGER_NAME}.tasks")


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

    task = MusicTask(
        status=TaskStatus.PENDING.value,
        operation="generate",
        provider="suno",
        model=settings.SUNO_MODEL or None,
        requested_by_id=requested_by_id,
        lyrics_version_id=lyrics_version.id,
        title=(payload.title or lyrics_version.title).strip(),
        lyrics="" if payload.instrumental else lyrics_version.content,
        style_prompt=(payload.style_prompt or lyrics_version.style_prompt).strip(),
        instrumental=payload.instrumental,
        negative_tags=payload.negative_tags,
        requirements=_clean_optional_text(payload.requirements),
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
    task = MusicTask(
        status=TaskStatus.PENDING.value,
        operation="extend",
        provider="suno",
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
    )
    db.add(task)
    db.commit()
    return get_music_task(db, task.id)


def execute_music_task(
    task_id: int,
    bind: Engine | Connection,
) -> None:
    session_factory = sessionmaker(bind=bind, autocommit=False, autoflush=False)
    with session_factory() as db:
        execute_music_task_in_session(db, task_id)


def execute_music_task_in_session(db: Session, task_id: int) -> None:
    task = _load_task(db, task_id)
    if task is None or task.status != TaskStatus.PENDING.value:
        return
    task.status = TaskStatus.RUNNING.value
    task.started_at = utc_now()
    task.error_code = None
    task.error_message = None
    task.error_detail = None
    db.commit()
    task_logger.info(
        "music_task_started",
        extra={"task_id": str(task.id), "task_type": "music"},
    )

    try:
        provider = get_music_provider()
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
        output = (
            provider.extend(provider_payload)
            if task.operation == "extend"
            else provider.generate(provider_payload)
        )
        _complete_music_task(db, task, output)
    except MusicProviderError as exc:
        _fail_music_task(db, task, exc)
    except Exception:
        task_logger.exception(
            "music_task_failed",
            extra={
                "task_id": str(task.id),
                "task_type": "music",
                "error_code": "MUSIC_UNEXPECTED_ERROR",
            },
        )
        _fail_music_task(
            db,
            task,
            MusicProviderError(
                "音乐生成发生未预期错误，请按任务编号检索日志",
                code="MUSIC_UNEXPECTED_ERROR",
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
            _delete_storage_file(result.storage_key)
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
    _delete_storage_file(result.storage_key)
    db.delete(result)
    db.commit()


def get_music_result(db: Session, result_id: int) -> MusicResult:
    return _get_result(db, result_id)


def resolve_storage_path(storage_key: str | None) -> Path | None:
    if not storage_key:
        return None
    root = _storage_root()
    candidate = (root / storage_key).resolve()
    if root != candidate and root not in candidate.parents:
        return None
    return candidate if candidate.is_file() else None


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
            result.storage_key = _download_audio(
                task.id,
                result.id,
                track.audio_url,
                result.media_type,
            )
        except (httpx.HTTPError, OSError, ValueError) as exc:
            result.storage_error = f"音频归档失败（{type(exc).__name__}）"

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
    task.completed_at = utc_now()
    db.commit()
    task_logger.info(
        "music_task_completed",
        extra={"task_id": str(task.id), "task_type": "music"},
    )


def _fail_music_task(
    db: Session,
    task: MusicTask,
    error: MusicProviderError,
) -> None:
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
    task.status = TaskStatus.FAILED.value
    task.error_code = error.code
    task.error_message = str(error)
    task.error_detail = error.detail
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


def _load_task(db: Session, task_id: int) -> MusicTask | None:
    return db.scalar(
        select(MusicTask)
        .options(selectinload(MusicTask.results))
        .where(MusicTask.id == task_id)
    )


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


def _storage_root() -> Path:
    root = Path(settings.MUSIC_STORAGE_DIR).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _download_audio(
    task_id: int,
    result_id: int,
    url: str,
    media_type: str,
) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Suno 音频地址不是有效 HTTPS URL")
    extension = {
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/mp4": ".m4a",
        "audio/m4a": ".m4a",
    }.get(media_type.lower(), ".mp3")
    relative = Path(str(task_id)) / f"{result_id}{extension}"
    destination = _storage_root() / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    try:
        with httpx.stream(
            "GET",
            url,
            follow_redirects=True,
            timeout=settings.SUNO_DOWNLOAD_TIMEOUT_SECONDS,
        ) as response:
            response.raise_for_status()
            with destination.open("wb") as output:
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > settings.SUNO_MAX_AUDIO_BYTES:
                        raise ValueError("Suno 音频文件超过允许大小")
                    output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return relative.as_posix()


def _delete_storage_file(storage_key: str | None) -> None:
    path = resolve_storage_path(storage_key)
    if path is not None:
        path.unlink(missing_ok=True)
        try:
            path.parent.rmdir()
        except OSError:
            pass


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None
