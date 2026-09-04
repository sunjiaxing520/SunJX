import logging
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, selectinload

from app.adapters.text_generation import (
    GeneratedLyricsMemoryInsight,
    TextGenerationProvider,
    TextProviderError,
)
from app.core.exceptions import AppException
from app.core.logging import LOGGER_NAME
from app.models import (
    AnalysisReport,
    FavoriteItem,
    LyricsAssistantMessage,
    LyricsTask,
    LyricsVersion,
    TaskStatus,
    WorkflowRunStep,
    WorkflowStepType,
)
from app.schemas.lyrics import (
    CreationBriefResponse,
    LyricsCreateRequest,
    LyricsAssistantHistoryResponse,
    LyricsAssistantMessageRequest,
    LyricsAssistantMessageResponse,
    LyricsAssistantPreviewResponse,
    LyricsTaskDeleteResponse,
    LyricsTaskListResponse,
    LyricsTaskResponse,
    LyricsVersionResponse,
)
from app.services.api_usage import record_api_usage, task_api_usage
from app.services.ai_providers import resolve_text_provider
from app.services.lyrics_memory import (
    build_lyrics_skill_context,
    capture_accepted_result,
    capture_creation_request,
    capture_modification_request,
    capture_prompt_essence,
)
from app.services.lyrics_prompt import (
    screen_lyrics_prompt,
    screen_optional_lyrics_prompt,
)
from app.services.task_recovery import recover_stale_text_tasks


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


def lyrics_assistant_message_response(
    message: LyricsAssistantMessage,
) -> LyricsAssistantMessageResponse:
    preview = (
        LyricsAssistantPreviewResponse.model_validate(message.preview)
        if message.preview is not None
        else None
    )
    return LyricsAssistantMessageResponse(
        id=message.id,
        task_id=message.task_id,
        source_version_id=message.source_version_id,
        role=message.role,
        content=message.content,
        preview=preview,
        provider=message.provider,
        model=message.model,
        created_at=message.created_at,
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
    payload = payload.model_copy(
        update={
            "theme": screen_lyrics_prompt(
                payload.theme,
                field_name="歌曲主题",
                allow_short_topic=True,
            ),
            "requirements": screen_optional_lyrics_prompt(
                payload.requirements,
                field_name="补充要求",
            ),
        }
    )
    merged = _merge_analysis_direction(db, payload)
    try:
        provider = resolve_text_provider(db)
    except TextProviderError as exc:
        raise AppException(
            code="AI_PROVIDER_RUNTIME_INVALID",
            message="当前 AI 接口配置不可用，请联系超级管理员检查接口设置",
            status_code=503,
            detail={"reason": str(exc)},
        ) from exc
    task = LyricsTask(
        status=TaskStatus.PENDING.value,
        provider=provider.name,
        model=provider.model,
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
    capture_creation_request(
        db,
        task,
        user_id,
        request_data=payload.model_dump(include=payload.model_fields_set),
    )
    db.commit()
    _generate_version(db, task, variation=1, provider=provider)
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


def _generate_version(
    db: Session,
    task: LyricsTask,
    variation: int,
    provider: TextGenerationProvider | None = None,
) -> None:
    try:
        provider = provider or resolve_text_provider(db)
        task.provider = provider.name
        task.model = provider.model
        task.status = TaskStatus.RUNNING.value
        task.started_at = datetime.now(timezone.utc)
        task.error_code = None
        task.error_message = None
        db.commit()
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
            "lyrics_skill_memory": build_lyrics_skill_context(
                db,
                current_task_id=task.id,
            ),
        }
        generated_result = provider.generate_lyrics(context, variation)
        generated = generated_result.output
        requested_title = (task.title_hint or "").strip()
        if requested_title:
            generated.title = requested_title
        version = LyricsVersion(
            task_id=task.id,
            version_number=variation,
            title=generated.title,
            content=generated.content,
            style_prompt=generated.style_prompt,
            sections=[section.model_dump() for section in generated.sections],
            memory_insight=generated.memory_insight.model_dump(),
        )
        db.add(version)
        db.flush()
        capture_prompt_essence(
            db,
            task,
            generated.memory_insight,
            task.requested_by_id,
            source_kind="initial_creation",
            source_version_id=version.id,
        )
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
    recover_stale_text_tasks(db)
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
    recover_stale_text_tasks(db)
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


def delete_lyrics_task(db: Session, task_id: int) -> None:
    delete_lyrics_tasks(db, [task_id])


def delete_lyrics_tasks(
    db: Session,
    task_ids: list[int],
) -> LyricsTaskDeleteResponse:
    ordered_ids = list(dict.fromkeys(task_ids))
    tasks = db.scalars(
        select(LyricsTask)
        .options(selectinload(LyricsTask.versions))
        .where(LyricsTask.id.in_(ordered_ids))
        .with_for_update()
    ).all()
    tasks_by_id = {task.id: task for task in tasks}
    missing_ids = [task_id for task_id in ordered_ids if task_id not in tasks_by_id]
    if missing_ids:
        raise AppException(
            code="LYRICS_TASK_NOT_FOUND",
            message="部分作词记录不存在或已经被删除",
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
            code="LYRICS_TASK_DELETE_CONFLICT",
            message="运行中的作词任务不能删除，请等待任务结束后重试",
            status_code=409,
            detail={"active_task_ids": active_ids},
        )

    version_ids = [version.id for task in tasks for version in task.versions]
    if version_ids:
        db.execute(
            delete(FavoriteItem).where(
                FavoriteItem.item_type == "lyrics",
                FavoriteItem.target_id.in_(version_ids),
            )
        )
    db.execute(
        update(WorkflowRunStep)
        .where(
            WorkflowRunStep.step_type == WorkflowStepType.LYRICS.value,
            WorkflowRunStep.task_id.in_(ordered_ids),
        )
        .values(task_id=None, output_id=None)
    )
    if version_ids:
        db.execute(
            update(WorkflowRunStep)
            .where(
                WorkflowRunStep.step_type == WorkflowStepType.REVIEW.value,
                WorkflowRunStep.output_id.in_(version_ids),
            )
            .values(output_id=None)
        )
    for task_id in ordered_ids:
        db.delete(tasks_by_id[task_id])
    db.commit()
    return LyricsTaskDeleteResponse(
        deleted_count=len(ordered_ids),
        deleted_task_ids=ordered_ids,
    )


def save_lyrics_version(
    db: Session,
    version_id: int,
    user_id: int | None = None,
) -> LyricsVersionResponse:
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
    task = db.get(LyricsTask, version.task_id)
    if task is not None:
        capture_accepted_result(db, task, version, user_id)
    db.commit()
    db.refresh(version)
    return lyrics_version_response(version)


def list_lyrics_assistant_messages(
    db: Session,
    version_id: int,
    *,
    review_run_id: int | None = None,
) -> LyricsAssistantHistoryResponse:
    _get_lyrics_version(db, version_id)
    query = select(LyricsAssistantMessage).where(
        LyricsAssistantMessage.source_version_id == version_id
    )
    query = query.where(
        LyricsAssistantMessage.review_run_id == review_run_id
        if review_run_id is not None
        else LyricsAssistantMessage.review_run_id.is_(None)
    )
    messages = db.scalars(
        query.order_by(LyricsAssistantMessage.created_at, LyricsAssistantMessage.id)
    ).all()
    return LyricsAssistantHistoryResponse(
        items=[lyrics_assistant_message_response(message) for message in messages]
    )


def create_lyrics_assistant_preview(
    db: Session,
    version_id: int,
    payload: LyricsAssistantMessageRequest,
    user_id: int,
    *,
    review_guidance: str | None = None,
    review_run_id: int | None = None,
) -> LyricsAssistantMessageResponse:
    version = _get_lyrics_version(db, version_id)
    task = db.get(LyricsTask, version.task_id)
    if task is None:
        raise AppException(
            code="LYRICS_TASK_NOT_FOUND", message="作词任务不存在", status_code=404
        )
    instruction = screen_lyrics_prompt(
        payload.instruction,
        field_name="歌词修改要求",
    )

    user_message = LyricsAssistantMessage(
        task_id=task.id,
        source_version_id=version.id,
        review_run_id=review_run_id,
        role="user",
        content=instruction,
        created_by_id=user_id,
    )
    db.add(user_message)
    db.flush()
    capture_modification_request(
        db,
        task,
        version,
        instruction,
        user_id,
        review_guidance=review_guidance,
        review_run_id=review_run_id,
        message_id=user_message.id,
    )
    db.commit()

    try:
        provider = resolve_text_provider(db)
        history = _assistant_context_history(
            db,
            version.id,
            review_run_id=review_run_id,
        )
        generated_result = provider.revise_lyrics(
            {
                "task": {
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
                },
                "original": {
                    "title": version.title,
                    "content": version.content,
                    "style_prompt": version.style_prompt,
                    "sections": version.sections,
                },
                "history": history,
                "lyrics_skill_memory": build_lyrics_skill_context(
                    db,
                    current_task_id=task.id,
                ),
                "review_guidance": review_guidance,
                "instruction": instruction,
                "variation": len(task.versions) + len(history) + 1,
            }
        )
        generated = generated_result.output
        assistant_message = LyricsAssistantMessage(
            task_id=task.id,
            source_version_id=version.id,
            review_run_id=review_run_id,
            role="assistant",
            content="已生成一份预览，确认满意后再保存为正式版本。",
            preview={
                "title": generated.title,
                "content": generated.content,
                "style_prompt": generated.style_prompt,
                "sections": [section.model_dump() for section in generated.sections],
                "memory_insight": generated.memory_insight.model_dump(),
            },
            provider=provider.name,
            model=provider.model,
            created_by_id=user_id,
        )
        db.add(assistant_message)
        db.flush()
        capture_prompt_essence(
            db,
            task,
            generated.memory_insight,
            user_id,
            source_kind="revision",
            source_version_id=version.id,
            message_id=user_message.id,
        )
        record_api_usage(
            db,
            task_type="lyrics",
            task_id=task.id,
            operation="lyrics.assistant_preview",
            provider=provider.name,
            model=provider.model,
            call=generated_result.call,
            status=TaskStatus.COMPLETED.value,
        )
        db.commit()
        db.refresh(assistant_message)
        return lyrics_assistant_message_response(assistant_message)
    except (TextProviderError, ValueError) as exc:
        db.rollback()
        record_api_usage(
            db,
            task_type="lyrics",
            task_id=task.id,
            operation="lyrics.assistant_preview",
            provider=task.provider,
            model=task.model,
            call=getattr(exc, "call", None),
            status=TaskStatus.FAILED.value,
            error_code="LYRICS_ASSISTANT_FAILED",
            error_message=str(exc),
        )
        db.commit()
        raise AppException(
            code="LYRICS_ASSISTANT_FAILED",
            message="歌词 AI 助手生成预览失败，请查看接口用量记录",
            status_code=502,
            detail={"task_id": task.id, "reason": str(exc)},
        ) from exc


def confirm_lyrics_assistant_preview(
    db: Session,
    message_id: int,
    user_id: int | None = None,
) -> LyricsVersionResponse:
    message = db.get(LyricsAssistantMessage, message_id)
    if message is None or message.role != "assistant" or message.preview is None:
        raise AppException(
            code="LYRICS_ASSISTANT_PREVIEW_NOT_FOUND",
            message="歌词 AI 助手预览不存在",
            status_code=404,
        )
    try:
        preview = LyricsAssistantPreviewResponse.model_validate(message.preview)
    except ValueError as exc:
        raise AppException(
            code="LYRICS_ASSISTANT_PREVIEW_INVALID",
            message="歌词 AI 助手预览格式无效，无法保存",
            status_code=409,
        ) from exc
    task = db.get(LyricsTask, message.task_id)
    if task is None:
        raise AppException(
            code="LYRICS_TASK_NOT_FOUND", message="作词任务不存在", status_code=404
        )
    source_version = db.get(LyricsVersion, message.source_version_id)
    raw_memory_insight = message.preview.get("memory_insight")
    memory_insight = (
        GeneratedLyricsMemoryInsight.model_validate(raw_memory_insight).model_dump()
        if raw_memory_insight is not None
        else None
    )
    previous_user_message = db.scalar(
        select(LyricsAssistantMessage)
        .where(
            LyricsAssistantMessage.source_version_id == message.source_version_id,
            LyricsAssistantMessage.review_run_id == message.review_run_id,
            LyricsAssistantMessage.role == "user",
            LyricsAssistantMessage.id < message.id,
        )
        .order_by(LyricsAssistantMessage.id.desc())
        .limit(1)
    )
    next_version = (
        db.scalar(
            select(func.max(LyricsVersion.version_number)).where(
                LyricsVersion.task_id == task.id
            )
        )
        or 0
    ) + 1
    db.execute(
        update(LyricsVersion)
        .where(LyricsVersion.task_id == task.id)
        .values(is_saved=False)
    )
    version = LyricsVersion(
        task_id=task.id,
        version_number=next_version,
        title=preview.title,
        content=preview.content,
        style_prompt=preview.style_prompt,
        sections=preview.sections,
        memory_insight=memory_insight,
        is_saved=True,
    )
    db.add(version)
    db.flush()
    capture_accepted_result(
        db,
        task,
        version,
        user_id if user_id is not None else message.created_by_id,
        instruction=(
            previous_user_message.content if previous_user_message is not None else None
        ),
        source_version=source_version,
    )
    db.commit()
    db.refresh(version)
    return lyrics_version_response(version)


def _assistant_context_history(
    db: Session,
    version_id: int,
    *,
    review_run_id: int | None = None,
) -> list[dict[str, object]]:
    query = select(LyricsAssistantMessage).where(
        LyricsAssistantMessage.source_version_id == version_id
    )
    query = query.where(
        LyricsAssistantMessage.review_run_id == review_run_id
        if review_run_id is not None
        else LyricsAssistantMessage.review_run_id.is_(None)
    )
    messages = db.scalars(
        query.order_by(
            LyricsAssistantMessage.created_at.desc(),
            LyricsAssistantMessage.id.desc(),
        )
        .limit(8)
    ).all()
    history: list[dict[str, object]] = []
    for message in reversed(messages):
        entry: dict[str, object] = {"role": message.role, "content": message.content}
        if message.preview is not None:
            entry["preview"] = message.preview
        history.append(entry)
    return history


def _get_lyrics_version(db: Session, version_id: int) -> LyricsVersion:
    version = db.get(LyricsVersion, version_id)
    if version is None:
        raise AppException(
            code="LYRICS_VERSION_NOT_FOUND", message="歌词版本不存在", status_code=404
        )
    return version


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
