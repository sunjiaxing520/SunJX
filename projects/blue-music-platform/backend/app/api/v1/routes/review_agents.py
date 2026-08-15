from fastapi import APIRouter, Query, status

from app.api.dependencies import CurrentUser, DatabaseSession, SuperAdmin
from app.models import User
from app.schemas.review_agent import (
    ReviewAgentCreateRequest,
    ReviewAgentInitializationPreviewRequest,
    ReviewAgentInitializationPreviewResponse,
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
from app.services.review_agents import (
    create_lyrics_review,
    create_review_agent,
    get_review_agent,
    list_review_agents,
    list_review_lyrics_options,
    list_review_runs,
    preview_review_agent_initialization,
    replace_review_agent_members,
    save_review_agent_memory,
    update_review_agent_settings,
)


router = APIRouter(prefix="/review-agents")


@router.post(
    "/initialize-preview",
    response_model=ReviewAgentInitializationPreviewResponse,
)
def review_agent_initialize_preview(
    payload: ReviewAgentInitializationPreviewRequest,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> ReviewAgentInitializationPreviewResponse:
    return preview_review_agent_initialization(db, payload)


@router.post("", response_model=ReviewAgentResponse, status_code=status.HTTP_201_CREATED)
def review_agent_create(
    payload: ReviewAgentCreateRequest,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> ReviewAgentResponse:
    return create_review_agent(db, payload, admin.id)


@router.get("", response_model=list[ReviewAgentResponse])
def review_agent_list(
    db: DatabaseSession,
    user: CurrentUser,
) -> list[ReviewAgentResponse]:
    return list_review_agents(db, user)


@router.get("/lyrics-options", response_model=list[ReviewLyricsOption])
def review_agent_lyrics_options(
    db: DatabaseSession,
    user: CurrentUser,
    limit: int = Query(default=100, ge=1, le=100),
) -> list[ReviewLyricsOption]:
    return list_review_lyrics_options(db, user, limit)


@router.get("/{agent_id}", response_model=ReviewAgentResponse)
def review_agent_detail(
    agent_id: int,
    db: DatabaseSession,
    user: CurrentUser,
) -> ReviewAgentResponse:
    return get_review_agent(db, agent_id, user)


@router.patch("/{agent_id}/settings", response_model=ReviewAgentResponse)
def review_agent_settings(
    agent_id: int,
    payload: ReviewAgentSettingsUpdate,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> ReviewAgentResponse:
    return update_review_agent_settings(db, agent_id, payload)


@router.put("/{agent_id}/members", response_model=ReviewAgentResponse)
def review_agent_members(
    agent_id: int,
    payload: ReviewAgentMemberUpdate,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> ReviewAgentResponse:
    return replace_review_agent_members(db, agent_id, payload)


@router.post("/{agent_id}/reviews", response_model=ReviewResultResponse)
def review_agent_review_lyrics(
    agent_id: int,
    payload: ReviewCreateRequest,
    db: DatabaseSession,
    user: CurrentUser,
) -> ReviewResultResponse:
    return create_lyrics_review(db, agent_id, payload, user)


@router.get("/{agent_id}/reviews", response_model=ReviewListResponse)
def review_agent_review_history(
    agent_id: int,
    db: DatabaseSession,
    user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> ReviewListResponse:
    return list_review_runs(db, agent_id, user, limit)


@router.post("/{agent_id}/memory", response_model=ReviewMemoryResponse)
def review_agent_save_memory(
    agent_id: int,
    payload: ReviewMemorySaveRequest,
    db: DatabaseSession,
    user: CurrentUser,
) -> ReviewMemoryResponse:
    return save_review_agent_memory(db, agent_id, payload, user)
