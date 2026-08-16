import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.adapters.text_generation import TextProviderError
from app.core.exceptions import AppException
from app.models import (
    LyricsAssistantMessage,
    LyricsTask,
    LyricsVersion,
    ReviewAgent,
    ReviewAgentMember,
    ReviewRun,
    TaskStatus,
    User,
    UserRole,
)
from app.schemas.lyrics import (
    LyricsAssistantHistoryResponse,
    LyricsAssistantMessageRequest,
    LyricsAssistantMessageResponse,
    LyricsVersionResponse,
)
from app.schemas.review_agent import (
    ReviewAgentCreateRequest,
    ReviewAgentInitializationPreviewRequest,
    ReviewAgentInitializationPreviewResponse,
    ReviewAgentMemberResponse,
    ReviewAgentMemberUpdate,
    ReviewAgentResponse,
    ReviewAgentSettingsUpdate,
    ReviewCreateRequest,
    ReviewLyricsOption,
    ReviewListResponse,
    ReviewMemoryResponse,
    ReviewMemorySaveRequest,
    ReviewResultResponse,
)
from app.services.ai_providers import resolve_text_provider
from app.services.api_usage import record_api_usage
from app.services.lyrics import (
    confirm_lyrics_assistant_preview,
    create_lyrics_assistant_preview,
    list_lyrics_assistant_messages,
)


def preview_review_agent_initialization(
    db: Session,
    payload: ReviewAgentInitializationPreviewRequest,
) -> ReviewAgentInitializationPreviewResponse:
    provider = _resolve_provider(db)
    messages = [
        *[message.model_dump() for message in payload.messages],
        {"role": "user", "content": payload.message.strip()},
    ]
    try:
        generated = provider.initialize_review_agent(messages).output
    except TextProviderError as exc:
        raise _provider_error("REVIEW_AGENT_INITIALIZATION_FAILED", exc) from exc
    return ReviewAgentInitializationPreviewResponse(
        reply=generated.reply,
        summary=generated.summary,
        detail=generated.detail,
    )


def create_review_agent(
    db: Session,
    payload: ReviewAgentCreateRequest,
    user_id: int,
) -> ReviewAgentResponse:
    provider = _resolve_provider(db)
    messages = [message.model_dump() for message in payload.initialization_messages]
    try:
        generated_result = provider.initialize_review_agent(messages)
    except TextProviderError as exc:
        raise _provider_error("REVIEW_AGENT_INITIALIZATION_FAILED", exc) from exc

    agent = ReviewAgent(
        name=payload.name,
        pass_score=payload.pass_score,
        initialization_notes="\n".join(
            f"{message['role']}: {message['content']}" for message in messages
        ),
        memory_summary=generated_result.output.summary,
        memory_detail=generated_result.output.detail,
        created_by_id=user_id,
    )
    db.add(agent)
    db.flush()
    record_api_usage(
        db,
        task_type="review_agent",
        task_id=agent.id,
        operation="review_agent.initialize",
        provider=provider.name,
        model=provider.model,
        call=generated_result.call,
        status=TaskStatus.COMPLETED.value,
    )
    db.commit()
    db.refresh(agent)
    return review_agent_response(db, agent, include_memory_detail=True)


def list_review_agents(db: Session, user: User) -> list[ReviewAgentResponse]:
    query = select(ReviewAgent).options(selectinload(ReviewAgent.members))
    if user.role != UserRole.SUPER_ADMIN:
        query = query.join(ReviewAgentMember).where(
            ReviewAgentMember.user_id == user.id
        )
    agents = db.scalars(query.order_by(ReviewAgent.updated_at.desc(), ReviewAgent.id.desc())).all()
    return [
        review_agent_response(
            db,
            agent,
            include_memory_detail=user.role == UserRole.SUPER_ADMIN,
        )
        for agent in agents
    ]


def get_review_agent(
    db: Session,
    agent_id: int,
    user: User,
) -> ReviewAgentResponse:
    agent = require_review_agent_access(db, agent_id, user)
    return review_agent_response(
        db,
        agent,
        include_memory_detail=user.role == UserRole.SUPER_ADMIN,
    )


def replace_review_agent_members(
    db: Session,
    agent_id: int,
    payload: ReviewAgentMemberUpdate,
) -> ReviewAgentResponse:
    agent = _get_agent(db, agent_id)
    users = db.scalars(select(User).where(User.id.in_(payload.user_ids))).all()
    found_ids = {user.id for user in users}
    missing_ids = [user_id for user_id in payload.user_ids if user_id not in found_ids]
    if missing_ids:
        raise AppException(
            code="REVIEW_AGENT_MEMBER_NOT_FOUND",
            message="部分成员不存在",
            status_code=404,
            detail={"missing_user_ids": missing_ids},
        )
    agent.members.clear()
    agent.members.extend(ReviewAgentMember(user_id=user_id) for user_id in payload.user_ids)
    db.commit()
    db.refresh(agent)
    return review_agent_response(db, agent, include_memory_detail=True)


def update_review_agent_settings(
    db: Session,
    agent_id: int,
    payload: ReviewAgentSettingsUpdate,
) -> ReviewAgentResponse:
    agent = _get_agent(db, agent_id)
    agent.pass_score = payload.pass_score
    db.commit()
    db.refresh(agent)
    return review_agent_response(db, agent, include_memory_detail=True)


def list_review_lyrics_options(
    db: Session,
    user: User,
    limit: int = 100,
) -> list[ReviewLyricsOption]:
    _ensure_has_any_review_access(db, user)
    rows = db.execute(
        select(LyricsVersion, LyricsTask)
        .join(LyricsTask, LyricsTask.id == LyricsVersion.task_id)
        .order_by(LyricsVersion.created_at.desc(), LyricsVersion.id.desc())
        .limit(limit)
    ).all()
    return [
        ReviewLyricsOption(
            id=version.id,
            task_id=version.task_id,
            version_number=version.version_number,
            title=version.title,
            theme=task.theme,
            content=version.content,
            style_prompt=version.style_prompt,
            is_saved=version.is_saved,
            provider=task.provider,
            model=task.model,
            created_at=version.created_at,
        )
        for version, task in rows
    ]


def create_lyrics_review(
    db: Session,
    agent_id: int,
    payload: ReviewCreateRequest,
    user: User,
) -> ReviewResultResponse:
    agent = require_review_agent_access(db, agent_id, user)
    version = db.get(LyricsVersion, payload.lyrics_version_id)
    if version is None:
        raise AppException(
            code="LYRICS_VERSION_NOT_FOUND", message="歌词版本不存在", status_code=404
        )
    provider = _resolve_provider(db)
    try:
        generated_result = provider.review_lyrics(
            {
                "agent_name": agent.name,
                "pass_score": agent.pass_score,
                "memory_summary": agent.memory_summary,
                "memory_detail": agent.memory_detail,
                "lyrics": {
                    "title": version.title,
                    "content": version.content,
                    "style_prompt": version.style_prompt,
                    "sections": version.sections,
                },
                "instruction": payload.instruction,
            }
        )
    except TextProviderError as exc:
        raise _provider_error("REVIEW_AGENT_EXECUTION_FAILED", exc) from exc
    result = generated_result.output.model_dump()
    result["pass_score"] = agent.pass_score
    result["passed"] = generated_result.output.overall_score >= agent.pass_score
    if not result["passed"]:
        deduction_reasons = list(result.get("deduction_reasons") or [])
        if not deduction_reasons:
            deduction_reasons = [
                f"{dimension.name} {dimension.score} 分：{dimension.feedback}"
                for dimension in generated_result.output.dimensions
                if dimension.score < agent.pass_score
            ]
        if not deduction_reasons:
            deduction_reasons = [generated_result.output.summary]
        result["deduction_reasons"] = deduction_reasons[:12]

        suggestions = list(result.get("revision_suggestions") or [])
        if not suggestions:
            suggestions = [
                dimension.feedback
                for dimension in generated_result.output.dimensions
                if dimension.score < agent.pass_score
            ]
        result["revision_suggestions"] = suggestions[:12]

    run = ReviewRun(
        agent_id=agent.id,
        lyrics_version_id=version.id,
        requested_by_id=user.id,
        instruction=_clean_optional_text(payload.instruction),
        provider=provider.name,
        model=provider.model,
        result=result,
    )
    db.add(run)
    db.flush()
    record_api_usage(
        db,
        task_type="review",
        task_id=run.id,
        operation="review_agent.review_lyrics",
        provider=provider.name,
        model=provider.model,
        call=generated_result.call,
        status=TaskStatus.COMPLETED.value,
    )
    db.commit()
    db.refresh(run)
    return review_result_response(run)


def list_review_runs(
    db: Session,
    agent_id: int,
    user: User,
    limit: int = 20,
) -> ReviewListResponse:
    require_review_agent_access(db, agent_id, user)
    query = select(ReviewRun).where(ReviewRun.agent_id == agent_id)
    runs = db.scalars(
        query.order_by(ReviewRun.created_at.desc(), ReviewRun.id.desc()).limit(limit)
    ).all()
    total = db.scalar(select(func.count(ReviewRun.id)).where(ReviewRun.agent_id == agent_id)) or 0
    return ReviewListResponse(
        items=[review_result_response(run) for run in runs],
        total=total,
    )


def get_review_run(
    db: Session,
    agent_id: int,
    review_id: int,
    user: User,
) -> ReviewResultResponse:
    return review_result_response(_get_review_run(db, agent_id, review_id, user))


def list_review_revision_messages(
    db: Session,
    agent_id: int,
    review_id: int,
    user: User,
) -> LyricsAssistantHistoryResponse:
    run, version = _review_revision_source(db, agent_id, review_id, user)
    return list_lyrics_assistant_messages(
        db,
        version.id,
        review_run_id=run.id,
    )


def create_review_revision_preview(
    db: Session,
    agent_id: int,
    review_id: int,
    payload: LyricsAssistantMessageRequest,
    user: User,
) -> LyricsAssistantMessageResponse:
    run, version = _review_revision_source(db, agent_id, review_id, user)
    return create_lyrics_assistant_preview(
        db,
        version.id,
        payload,
        user.id,
        review_guidance=_review_revision_guidance(run),
        review_run_id=run.id,
    )


def confirm_review_revision_preview(
    db: Session,
    agent_id: int,
    review_id: int,
    message_id: int,
    user: User,
) -> LyricsVersionResponse:
    _, version = _review_revision_source(db, agent_id, review_id, user)
    message = db.get(LyricsAssistantMessage, message_id)
    if (
        message is None
        or message.source_version_id != version.id
        or message.review_run_id != review_id
    ):
        raise AppException(
            code="REVIEW_REVISION_PREVIEW_NOT_FOUND",
            message="当前审核记录下没有这份歌词修改预览",
            status_code=404,
            detail={"review_id": review_id, "message_id": message_id},
        )
    return confirm_lyrics_assistant_preview(db, message_id)


def save_review_agent_memory(
    db: Session,
    agent_id: int,
    payload: ReviewMemorySaveRequest,
    user: User,
) -> ReviewMemoryResponse:
    agent = require_review_agent_access(db, agent_id, user)
    provider = _resolve_provider(db)
    try:
        generated_result = provider.summarize_review_memory(
            {
                "existing_summary": agent.memory_summary,
                "existing_memory": agent.memory_detail,
                "content": payload.content,
            }
        )
    except TextProviderError as exc:
        raise _provider_error("REVIEW_AGENT_MEMORY_FAILED", exc) from exc
    agent.memory_summary = generated_result.output.summary
    agent.memory_detail = generated_result.output.detail
    record_api_usage(
        db,
        task_type="review_memory",
        task_id=agent.id,
        operation="review_agent.save_memory",
        provider=provider.name,
        model=provider.model,
        call=generated_result.call,
        status=TaskStatus.COMPLETED.value,
    )
    db.commit()
    return ReviewMemoryResponse(
        summary=agent.memory_summary,
        detail=agent.memory_detail if user.role == UserRole.SUPER_ADMIN else None,
    )


def require_review_agent_access(db: Session, agent_id: int, user: User) -> ReviewAgent:
    agent = _get_agent(db, agent_id)
    if user.role == UserRole.SUPER_ADMIN:
        return agent
    if not any(member.user_id == user.id for member in agent.members):
        raise AppException(
            code="REVIEW_AGENT_PERMISSION_DENIED",
            message="没有该审核智能体的使用权限",
            status_code=403,
        )
    return agent


def review_agent_response(
    db: Session,
    agent: ReviewAgent,
    *,
    include_memory_detail: bool,
) -> ReviewAgentResponse:
    member_ids = [member.user_id for member in agent.members]
    users = db.scalars(select(User).where(User.id.in_(member_ids))).all() if member_ids else []
    users_by_id = {user.id: user for user in users}
    return ReviewAgentResponse(
        id=agent.id,
        name=agent.name,
        pass_score=agent.pass_score,
        initialization_notes=(
            agent.initialization_notes if include_memory_detail else None
        ),
        memory_summary=agent.memory_summary,
        memory_detail=agent.memory_detail if include_memory_detail else None,
        created_by_id=agent.created_by_id,
        members=[
            ReviewAgentMemberResponse(id=member.user_id, username=users_by_id[member.user_id].username)
            for member in agent.members
            if member.user_id in users_by_id
        ],
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


def review_result_response(run: ReviewRun) -> ReviewResultResponse:
    return ReviewResultResponse(
        id=run.id,
        agent_id=run.agent_id,
        lyrics_version_id=run.lyrics_version_id,
        requested_by_id=run.requested_by_id,
        instruction=run.instruction,
        provider=run.provider,
        model=run.model,
        result=run.result,
        created_at=run.created_at,
    )


def _get_agent(db: Session, agent_id: int) -> ReviewAgent:
    agent = db.scalar(
        select(ReviewAgent)
        .options(selectinload(ReviewAgent.members))
        .where(ReviewAgent.id == agent_id)
    )
    if agent is None:
        raise AppException(
            code="REVIEW_AGENT_NOT_FOUND",
            message="审核智能体不存在",
            status_code=404,
        )
    return agent


def _review_revision_source(
    db: Session,
    agent_id: int,
    review_id: int,
    user: User,
) -> tuple[ReviewRun, LyricsVersion]:
    run = _get_review_run(db, agent_id, review_id, user)
    version = db.get(LyricsVersion, run.lyrics_version_id) if run.lyrics_version_id else None
    if version is None:
        raise AppException(
            code="REVIEW_LYRICS_VERSION_NOT_FOUND",
            message="被审核的歌词版本不存在，无法继续修改",
            status_code=409,
            detail={"review_id": review_id, "lyrics_version_id": run.lyrics_version_id},
        )
    return run, version


def _get_review_run(
    db: Session,
    agent_id: int,
    review_id: int,
    user: User,
) -> ReviewRun:
    require_review_agent_access(db, agent_id, user)
    run = db.scalar(
        select(ReviewRun).where(
            ReviewRun.id == review_id,
            ReviewRun.agent_id == agent_id,
        )
    )
    if run is None:
        raise AppException(
            code="REVIEW_RUN_NOT_FOUND",
            message="审核记录不存在",
            status_code=404,
        )
    return run


def _review_revision_guidance(run: ReviewRun) -> str:
    result = run.result if isinstance(run.result, dict) else {}
    guidance = {
        "summary": result.get("summary"),
        "overall_score": result.get("overall_score"),
        "pass_score": result.get("pass_score"),
        "dimensions": result.get("dimensions"),
        "deduction_reasons": result.get("deduction_reasons"),
        "revision_suggestions": result.get("revision_suggestions"),
        "risk_notes": result.get("risk_notes"),
    }
    serialized = json.dumps(guidance, ensure_ascii=False, separators=(",", ":"))
    return f"请根据本次歌词审核意见修改，不要忽略扣分原因和修改建议：{serialized}"[:6000]


def _ensure_has_any_review_access(db: Session, user: User) -> None:
    if user.role == UserRole.SUPER_ADMIN:
        return
    has_access = db.scalar(
        select(ReviewAgentMember.agent_id)
        .where(ReviewAgentMember.user_id == user.id)
        .limit(1)
    )
    if has_access is None:
        raise AppException(
            code="REVIEW_AGENT_PERMISSION_DENIED",
            message="没有可用审核智能体的使用权限",
            status_code=403,
        )


def _resolve_provider(db: Session):
    try:
        return resolve_text_provider(db)
    except TextProviderError as exc:
        raise AppException(
            code="AI_PROVIDER_RUNTIME_INVALID",
            message="当前 AI 接口配置不可用，请联系超级管理员检查接口设置",
            status_code=503,
            detail={"reason": str(exc)},
        ) from exc


def _provider_error(code: str, exc: TextProviderError) -> AppException:
    return AppException(
        code=code,
        message="审核智能体调用 AI 接口失败，请查看接口用量记录",
        status_code=502,
        detail={"reason": str(exc)},
    )


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None
