import logging

from fastapi import APIRouter, Query, Request, status

from app.api.dependencies import DatabaseSession, SuperAdmin
from app.core.logging import LOGGER_NAME
from app.core.request_context import get_request_id
from app.schemas.lyrics_memory import (
    LyricsMemoryChatListResponse,
    LyricsMemoryChatRequest,
    LyricsMemoryChatResultResponse,
    LyricsMemorySettingsRequest,
    LyricsTeamMemoryResponse,
)
from app.services.lyrics_memory import (
    edit_lyrics_team_memory,
    get_lyrics_team_memory,
    list_lyrics_memory_chat_messages,
    update_lyrics_memory_settings,
)


router = APIRouter(prefix="/lyrics-memory")
audit_logger = logging.getLogger(f"{LOGGER_NAME}.audit")


@router.get("", response_model=LyricsTeamMemoryResponse)
def lyrics_team_memory(
    db: DatabaseSession,
    admin: SuperAdmin,
) -> LyricsTeamMemoryResponse:
    return get_lyrics_team_memory(db)


@router.patch("/settings", response_model=LyricsTeamMemoryResponse)
def lyrics_memory_settings(
    request: Request,
    payload: LyricsMemorySettingsRequest,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> LyricsTeamMemoryResponse:
    result = update_lyrics_memory_settings(db, payload, admin.id)
    _audit(request, admin.id, "lyrics_memory_injection_limit_updated")
    return result


@router.get("/chat", response_model=LyricsMemoryChatListResponse)
def lyrics_memory_chat_history(
    db: DatabaseSession,
    admin: SuperAdmin,
    limit: int = Query(default=30, ge=1, le=100),
) -> LyricsMemoryChatListResponse:
    return list_lyrics_memory_chat_messages(db, limit=limit)


@router.post(
    "/chat",
    response_model=LyricsMemoryChatResultResponse,
    status_code=status.HTTP_201_CREATED,
)
def lyrics_memory_chat(
    request: Request,
    payload: LyricsMemoryChatRequest,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> LyricsMemoryChatResultResponse:
    result = edit_lyrics_team_memory(db, payload, admin.id)
    _audit(request, admin.id, "lyrics_memory_updated_by_chat")
    return result


def _audit(request: Request, user_id: int, event: str) -> None:
    audit_logger.info(
        event,
        extra={
            "request_id": get_request_id(request),
            "user_id": user_id,
        },
    )
