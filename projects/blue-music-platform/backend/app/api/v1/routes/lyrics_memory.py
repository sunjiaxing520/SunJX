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
    LyricsMemoryCompressionRequest,
    LyricsMemoryCompressionPreview,
)
from app.services.lyrics_memory import (
    edit_lyrics_team_memory,
    get_lyrics_team_memory,
    list_lyrics_memory_chat_messages,
    update_lyrics_memory_settings,
    preview_memory_compression,
    confirm_memory_compression,
)


router = APIRouter(prefix="/lyrics-memory")
audit_logger = logging.getLogger(f"{LOGGER_NAME}.audit")


@router.post("/compress", response_model=LyricsMemoryCompressionPreview)
def memory_compression_preview(payload: LyricsMemoryCompressionRequest, request: Request,
                               db: DatabaseSession, admin: SuperAdmin) -> LyricsMemoryCompressionPreview:
    result = preview_memory_compression(db, payload, admin.id)
    _audit(request, admin.id, "lyrics_memory_compression_preview_created")
    return result


@router.post("/compress/{preview_id}/confirm", response_model=LyricsTeamMemoryResponse)
def memory_compression_confirm(preview_id: int, request: Request,
                               db: DatabaseSession, admin: SuperAdmin) -> LyricsTeamMemoryResponse:
    result = confirm_memory_compression(db, preview_id, admin.id)
    _audit(request, admin.id, "lyrics_memory_compression_confirmed")
    return result


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
