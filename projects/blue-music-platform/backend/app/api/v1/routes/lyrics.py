from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import DatabaseSession, require_agent_permission
from app.models import AgentType, User
from app.schemas.lyrics import (
    CreationBriefResponse,
    LyricsAssistantHistoryResponse,
    LyricsAssistantMessageRequest,
    LyricsAssistantMessageResponse,
    LyricsComposeRequest,
    LyricsCreateRequest,
    LyricsTaskDeleteRequest,
    LyricsTaskDeleteResponse,
    LyricsTaskListResponse,
    LyricsTaskResponse,
    LyricsVersionResponse,
)
from app.services.lyrics import (
    compose_lyrics,
    confirm_lyrics_assistant_preview,
    create_lyrics_assistant_preview,
    create_lyrics_task,
    delete_lyrics_task,
    delete_lyrics_tasks,
    get_creation_brief,
    get_lyrics_task,
    list_lyrics_tasks,
    list_lyrics_assistant_messages,
    regenerate_lyrics,
    save_lyrics_version,
)


router = APIRouter(prefix="/lyrics")
LyricsUser = Annotated[User, Depends(require_agent_permission(AgentType.LYRICS))]


@router.post("/compose", response_model=LyricsTaskResponse, status_code=201)
def lyrics_compose(
    payload: LyricsComposeRequest,
    db: DatabaseSession,
    user: LyricsUser,
) -> LyricsTaskResponse:
    return compose_lyrics(db, payload, user.id)


@router.post(
    "/tasks",
    response_model=LyricsTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_lyrics(
    payload: LyricsCreateRequest,
    db: DatabaseSession,
    user: LyricsUser,
) -> LyricsTaskResponse:
    return create_lyrics_task(db, payload, user.id)


@router.get("/tasks", response_model=LyricsTaskListResponse)
def lyrics_history(
    db: DatabaseSession,
    user: LyricsUser,
    limit: int = Query(default=15, ge=1, le=100),
) -> LyricsTaskListResponse:
    return list_lyrics_tasks(db, limit)


@router.delete("/tasks", response_model=LyricsTaskDeleteResponse)
def lyrics_bulk_delete(
    payload: LyricsTaskDeleteRequest,
    db: DatabaseSession,
    user: LyricsUser,
) -> LyricsTaskDeleteResponse:
    return delete_lyrics_tasks(db, payload.task_ids)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def lyrics_delete(
    task_id: int,
    db: DatabaseSession,
    user: LyricsUser,
) -> Response:
    delete_lyrics_task(db, task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tasks/{task_id}", response_model=LyricsTaskResponse)
def lyrics_detail(
    task_id: int,
    db: DatabaseSession,
    user: LyricsUser,
) -> LyricsTaskResponse:
    return get_lyrics_task(db, task_id)


@router.post(
    "/tasks/{task_id}/regenerate",
    response_model=LyricsTaskResponse,
)
def lyrics_regenerate(
    task_id: int,
    db: DatabaseSession,
    user: LyricsUser,
) -> LyricsTaskResponse:
    return regenerate_lyrics(db, task_id)


@router.put(
    "/versions/{version_id}/save",
    response_model=LyricsVersionResponse,
)
def lyrics_save(
    version_id: int,
    db: DatabaseSession,
    user: LyricsUser,
) -> LyricsVersionResponse:
    return save_lyrics_version(db, version_id, user.id)


@router.get(
    "/versions/{version_id}/assistant",
    response_model=LyricsAssistantHistoryResponse,
)
def lyrics_assistant_history(
    version_id: int,
    db: DatabaseSession,
    user: LyricsUser,
) -> LyricsAssistantHistoryResponse:
    return list_lyrics_assistant_messages(db, version_id)


@router.post(
    "/versions/{version_id}/assistant",
    response_model=LyricsAssistantMessageResponse,
)
def lyrics_assistant_preview(
    version_id: int,
    payload: LyricsAssistantMessageRequest,
    db: DatabaseSession,
    user: LyricsUser,
) -> LyricsAssistantMessageResponse:
    return create_lyrics_assistant_preview(db, version_id, payload, user.id)


@router.post(
    "/assistant-previews/{message_id}/confirm",
    response_model=LyricsVersionResponse,
)
def lyrics_assistant_confirm(
    message_id: int,
    db: DatabaseSession,
    user: LyricsUser,
) -> LyricsVersionResponse:
    return confirm_lyrics_assistant_preview(db, message_id, user.id)


@router.get(
    "/versions/{version_id}/creation-brief",
    response_model=CreationBriefResponse,
)
def creation_brief(
    version_id: int,
    db: DatabaseSession,
    user: LyricsUser,
) -> CreationBriefResponse:
    return get_creation_brief(db, version_id)
