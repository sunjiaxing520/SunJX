import logging
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.adapters.text_generation import TextProviderError, get_text_provider
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import LOGGER_NAME
from app.models import AnalysisReport, LyricsTask, LyricsVersion, TaskStatus
from app.schemas.lyrics import (
    CreationBriefResponse,
    LyricsCreateRequest,
    LyricsTaskListResponse,
    LyricsTaskResponse,
    LyricsVersionResponse,
)
from app.services.api_usage import record_api_usage, task_api_usage


task_logger = logging.getLogger(f"{LOGGER_NAME}.tasks")


def lyrics_version_response(version: LyricsVersion) -> LyricsVersionResponse:
    return LyricsVersionResponse(
        id=version.id,
        task_id=version.task_id,
        version_number=version.version_number,
        title=version.title,
        content=version.content,
        style_prompt=version.style_prompt,
        sections=version.sections,
        is_saved=version.is_saved,
        created_at=version.created_at,
    )


def lyrics_task_response(db: Session, task: LyricsTask) -> LyricsTaskResponse:
    return LyricsTaskResponse(
        id=task.id,
        status=task.status,
        provider=task.provider,
        model=task.model,
        analysis_report_id=task.analysis_report_id,
        direction_index=task.direction_index,
        title_hint=task.title_hint,
        theme=task.theme,
        language=task.language,
        genre_tags=task.genre_tags,
        mood_tags=task.mood_tags,
        scene_tags=task.scene_tags,
        keywords=task.keywords,
        tempo=task.tempo,
        vocal_gender=task.vocal_gender,
        vocal_style=task.vocal_style,
        requirements=task.requirements,
        error_code=task.error_code,
        error_message=task.error_message,
        started_at=task.started_at,
        completed_at=task.completed_at,
        created_at=task.created_at,
        api_usage=task_api_usage(db, "lyrics", task.id),
        versions=[lyrics_version_response(version) for version in task.versions],
    )


def create_lyrics_task(
    db: Session,
    payload: LyricsCreateRequest,
    user_id: int,
) -> LyricsTaskResponse:
    merged = _merge_analysis_direction(db, payload)
    task = LyricsTask(
        status=TaskStatus.PENDING.value,
        provider=settings.AI_PROVIDER,
        model=settings.AI_MODEL or ("rules-v1" if settings.AI_PROVIDER == "local" else None),
        requested_by_id=user_id,
        analysis_report_id=payload.analysis_report_id,
        direction_index=payload.direction_index,
        title_hint=payload.title_hint,
        theme=payload.theme,
        language=payload.language,
        genre_tags=merged["genre_tags"],
        mood_tags=merged["mood_tags"],
        scene_tags=merged["scene_tags"],
        keywords=merged["keywords"],
        tempo=merged["tempo"],
        vocal_gender=merged["vocal_gender"],
        vocal_style=merged["vocal_style"],
        requirements=payload.requirements,
        reference_text=payload.reference_text,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    _generate_version(db, task, variation=1)
    return get_lyrics_task(db, task.id)


def regenerate_lyrics(db: Session, task_id: int) -> LyricsTaskResponse:
    task = db.scalar(
        select(LyricsTask)
        .options(selectinload(LyricsTask.versions))
        .where(LyricsTask.id == task_id)
    )
    if task is None:
        raise AppException(
            code="LYRICS_TASK_NOT_FOUND", message="作词任务不存在", status_code=404
        )
    _generate_version(db, task, variation=len(task.versions) + 1)
    return get_lyrics_task(db, task.id)


def _generate_version(db: Session, task: LyricsTask, variation: int) -> None:
    task.status = TaskStatus.RUNNING.value
    task.started_at = datetime.now(timezone.utc)
    task.error_code = None
    task.error_message = None
    db.commit()
    try:
        context = {
            "title_hint": task.title_hint,
            "theme": task.theme,
            "language": task.language,
            "genre_tags": task.genre_tags,
            "mood_tags": task.mood_tags,
            "scene_tags": task.scene_tags,
            "keywords": task.keywords,
            "tempo": task.tempo,
            "vocal_gender": task.vocal_gender,
            "vocal_style": task.vocal_style,
            "requirements": task.requirements,
            "reference_text": task.reference_text,
        }
        generated_result = get_text_provider().generate_lyrics(context, variation)
        generated = generated_result.output
        version = LyricsVersion(
            task_id=task.id,
            version_number=variation,
            title=generated.title,
            content=generated.content,
            style_prompt=generated.style_prompt,
            sections=generated.sections,
        )
        db.add(version)
        record_api_usage(
            db,
            task_type="lyrics",
            task_id=task.id,
            operation="lyrics.generate",
            provider=task.provider,
            model=task.model,
            call=generated_result.call,
            status=TaskStatus.COMPLETED.value,
        )
        task.status = TaskStatus.COMPLETED.value
        task.completed_at = datetime.now(timezone.utc)
        db.commit()
    except (TextProviderError, ValueError) as exc:
        db.rollback()
        _mark_lyrics_failed(
            db,
            task.id,
            "LYRICS_PROVIDER_FAILED",
            str(exc),
            call=getattr(exc, "call", None),
        )
        raise AppException(
            code="LYRICS_PROVIDER_FAILED",
            message="歌词生成失败，请查看任务记录中的具体原因",
            status_code=502,
            detail={"task_id": task.id, "reason": str(exc)},
        ) from exc
    except Exception as exc:
        db.rollback()
        task_logger.exception(
            "lyrics_task_failed",
            extra={"task_id": str(task.id), "error_code": "LYRICS_UNEXPECTED_ERROR"},
        )
        _mark_lyrics_failed(
            db,
            task.id,
            "LYRICS_UNEXPECTED_ERROR",
            "作词流程发生未预期错误，请按任务编号检索日志",
        )
        raise AppException(
            code="LYRICS_UNEXPECTED_ERROR",
            message="歌词生成失败，请稍后重试",
            status_code=500,
            detail={"task_id": task.id},
        ) from exc


def _merge_analysis_direction(
    db: Session, payload: LyricsCreateRequest
) -> dict[str, object]:
    direction: dict[str, object] = {}
    if payload.analysis_report_id is not None:
        report = db.get(AnalysisReport, payload.analysis_report_id)
        if report is None:
            raise AppException(
                code="LYRICS_ANALYSIS_NOT_FOUND",
                message="引用的分析报告不存在",
                status_code=404,
            )
        index = payload.direction_index or 0
        if index >= len(report.creation_directions):
            raise AppException(
                code="LYRICS_DIRECTION_NOT_FOUND",
                message="引用的创作方向不存在",
                status_code=422,
            )
        direction = report.creation_directions[index]

    return {
        "genre_tags": payload.genre_tags or list(direction.get("genre_tags") or []),
        "mood_tags": payload.mood_tags or list(direction.get("mood_tags") or []),
        "scene_tags": payload.scene_tags or list(direction.get("scene_tags") or []),
        "keywords": payload.keywords or list(direction.get("theme_keywords") or []),
        "tempo": payload.tempo or direction.get("tempo") or "medium",
        "vocal_gender": payload.vocal_gender or direction.get("vocal_gender") or "unspecified",
        "vocal_style": payload.vocal_style or direction.get("vocal_style") or "自然叙事人声",
    }


def _mark_lyrics_failed(
    db: Session,
    task_id: int,
    code: str,
    message: str,
    *,
    call=None,
) -> None:
    task = db.get(LyricsTask, task_id)
    if task is None:
        return
    task.status = TaskStatus.FAILED.value
    task.error_code = code
    task.error_message = message
    task.completed_at = datetime.now(timezone.utc)
    record_api_usage(
        db,
        task_type="lyrics",
        task_id=task.id,
        operation="lyrics.generate",
        provider=task.provider,
        model=task.model,
        call=call,
        status=TaskStatus.FAILED.value,
        error_code=code,
        error_message=message,
    )
    db.commit()


def get_lyrics_task(db: Session, task_id: int) -> LyricsTaskResponse:
    task = db.scalar(
        select(LyricsTask)
        .options(selectinload(LyricsTask.versions))
        .where(LyricsTask.id == task_id)
    )
    if task is None:
        raise AppException(
            code="LYRICS_TASK_NOT_FOUND", message="作词任务不存在", status_code=404
        )
    return lyrics_task_response(db, task)


def list_lyrics_tasks(db: Session, limit: int = 15) -> LyricsTaskListResponse:
    tasks = db.scalars(
        select(LyricsTask)
        .options(selectinload(LyricsTask.versions))
        .order_by(LyricsTask.created_at.desc(), LyricsTask.id.desc())
        .limit(limit)
    ).all()
    total = db.scalar(select(func.count(LyricsTask.id))) or 0
    return LyricsTaskListResponse(
        items=[lyrics_task_response(db, task) for task in tasks],
        total=total,
    )


def save_lyrics_version(db: Session, version_id: int) -> LyricsVersionResponse:
    version = db.get(LyricsVersion, version_id)
    if version is None:
        raise AppException(
            code="LYRICS_VERSION_NOT_FOUND", message="歌词版本不存在", status_code=404
        )
    db.execute(
        update(LyricsVersion)
        .where(LyricsVersion.task_id == version.task_id)
        .values(is_saved=False)
    )
    version.is_saved = True
    db.commit()
    db.refresh(version)
    return lyrics_version_response(version)


def get_creation_brief(db: Session, version_id: int) -> CreationBriefResponse:
    version = db.get(LyricsVersion, version_id)
    if version is None:
        raise AppException(
            code="LYRICS_VERSION_NOT_FOUND", message="歌词版本不存在", status_code=404
        )
    task = db.get(LyricsTask, version.task_id)
    if task is None:
        raise AppException(
            code="LYRICS_TASK_NOT_FOUND", message="作词任务不存在", status_code=404
        )
    direction: dict[str, object] = {}
    if task.analysis_report_id is not None:
        report = db.get(AnalysisReport, task.analysis_report_id)
        index = task.direction_index or 0
        if report is not None and index < len(report.creation_directions):
            direction = report.creation_directions[index]

    return CreationBriefResponse(
        title=version.title,
        language=task.language,
        genre_tags=task.genre_tags,
        mood_tags=task.mood_tags,
        theme_keywords=task.keywords,
        scene_tags=task.scene_tags,
        tempo=task.tempo or "medium",
        vocal_gender=task.vocal_gender or "unspecified",
        vocal_style=task.vocal_style or "自然叙事人声",
        instrument_tags=list(direction.get("instrument_tags") or []),
        structure=[section["name"] for section in version.sections],
        hook_direction=str(direction.get("hook_direction") or "突出副歌核心句"),
        lyrics=version.content,
        negative_constraints=list(direction.get("negative_constraints") or []),
        source_analysis_report_id=task.analysis_report_id,
        source_lyrics_version_id=version.id,
    )
