import logging

from fastapi import APIRouter, Query, Request, Response, status

from app.api.dependencies import DatabaseSession, SuperAdmin
from app.core.logging import LOGGER_NAME
from app.core.request_context import get_request_id
from app.schemas.lyrics_memory import (
    LyricsMemoryApplyResponse,
    LyricsMemoryBulkDeleteRequest,
    LyricsMemoryChatListResponse,
    LyricsMemoryChatMessageResponse,
    LyricsMemoryChatRequest,
    LyricsMemoryDeleteResponse,
    LyricsMemoryDistillResponse,
    LyricsMemoryEventDetailResponse,
    LyricsMemoryEventListResponse,
    LyricsMemoryEventType,
    LyricsMemoryManualRuleRequest,
    LyricsMemoryOverviewResponse,
    LyricsMemoryPreviewResponse,
    LyricsMemorySnapshotCreateRequest,
    LyricsMemorySnapshotDetailResponse,
    LyricsMemorySnapshotListResponse,
    LyricsMemorySnapshotSummaryResponse,
    LyricsMemorySnapshotUpdateRequest,
    LyricsMemoryUsefulnessRequest,
)
from app.services.lyrics_memory import (
    apply_lyrics_memory_chat_proposal,
    create_lyrics_memory_chat_preview,
    create_lyrics_memory_rule,
    create_lyrics_memory_snapshot,
    delete_lyrics_memory_event,
    delete_lyrics_memory_events,
    delete_lyrics_memory_snapshot,
    distill_next_legacy_lyrics_memory,
    get_lyrics_memory_event,
    get_lyrics_memory_overview,
    get_lyrics_memory_snapshot,
    list_lyrics_memory_events,
    list_lyrics_memory_chat_messages,
    list_lyrics_memory_snapshots,
    preview_lyrics_memory,
    set_lyrics_memory_event_usefulness,
    update_lyrics_memory_snapshot,
)


router = APIRouter(prefix="/lyrics-memory")
audit_logger = logging.getLogger(f"{LOGGER_NAME}.audit")


@router.get("/overview", response_model=LyricsMemoryOverviewResponse)
def lyrics_memory_overview(
    db: DatabaseSession,
    admin: SuperAdmin,
) -> LyricsMemoryOverviewResponse:
    return get_lyrics_memory_overview(db)


@router.get("/preview", response_model=LyricsMemoryPreviewResponse)
def lyrics_memory_preview(
    db: DatabaseSession,
    admin: SuperAdmin,
) -> LyricsMemoryPreviewResponse:
    return preview_lyrics_memory(db)


@router.post("/distill-pending", response_model=LyricsMemoryDistillResponse)
def lyrics_memory_distill_pending(
    request: Request,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> LyricsMemoryDistillResponse:
    result = distill_next_legacy_lyrics_memory(db)
    _audit(
        request,
        admin.id,
        "lyrics_memory_legacy_distilled",
        result.processed_event_ids,
    )
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
    response_model=LyricsMemoryChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def lyrics_memory_chat_preview(
    request: Request,
    payload: LyricsMemoryChatRequest,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> LyricsMemoryChatMessageResponse:
    result = create_lyrics_memory_chat_preview(db, payload, admin.id)
    _audit(request, admin.id, "lyrics_memory_chat_previewed", [result.id])
    return result


@router.post(
    "/chat/{message_id}/apply",
    response_model=LyricsMemoryApplyResponse,
)
def lyrics_memory_chat_apply(
    request: Request,
    message_id: int,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> LyricsMemoryApplyResponse:
    result = apply_lyrics_memory_chat_proposal(db, message_id, admin.id)
    _audit(
        request,
        admin.id,
        "lyrics_memory_chat_applied",
        [*result.created_event_ids, *result.updated_event_ids],
        chat_message_id=message_id,
    )
    return result


@router.get("/snapshots", response_model=LyricsMemorySnapshotListResponse)
def lyrics_memory_snapshots(
    db: DatabaseSession,
    admin: SuperAdmin,
) -> LyricsMemorySnapshotListResponse:
    return list_lyrics_memory_snapshots(db)


@router.post(
    "/snapshots",
    response_model=LyricsMemorySnapshotDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def lyrics_memory_snapshot_create(
    request: Request,
    payload: LyricsMemorySnapshotCreateRequest,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> LyricsMemorySnapshotDetailResponse:
    result = create_lyrics_memory_snapshot(db, payload, admin.id)
    _audit(request, admin.id, "lyrics_memory_snapshot_created", [result.id])
    return result


@router.get(
    "/snapshots/{snapshot_id}",
    response_model=LyricsMemorySnapshotDetailResponse,
)
def lyrics_memory_snapshot_detail(
    snapshot_id: int,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> LyricsMemorySnapshotDetailResponse:
    return get_lyrics_memory_snapshot(db, snapshot_id)


@router.put(
    "/snapshots/{snapshot_id}",
    response_model=LyricsMemorySnapshotSummaryResponse,
)
def lyrics_memory_snapshot_update(
    request: Request,
    snapshot_id: int,
    payload: LyricsMemorySnapshotUpdateRequest,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> LyricsMemorySnapshotSummaryResponse:
    result = update_lyrics_memory_snapshot(db, snapshot_id, payload)
    _audit(request, admin.id, "lyrics_memory_snapshot_renamed", [snapshot_id])
    return result


@router.delete(
    "/snapshots/{snapshot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def lyrics_memory_snapshot_delete(
    request: Request,
    snapshot_id: int,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> Response:
    delete_lyrics_memory_snapshot(db, snapshot_id)
    _audit(request, admin.id, "lyrics_memory_snapshot_deleted", [snapshot_id])
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/events", response_model=LyricsMemoryEventListResponse)
def lyrics_memory_events(
    db: DatabaseSession,
    admin: SuperAdmin,
    event_type: LyricsMemoryEventType | None = None,
    is_useful: bool | None = None,
    search: str = Query(default="", max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=15, ge=1, le=100),
) -> LyricsMemoryEventListResponse:
    return list_lyrics_memory_events(
        db,
        event_type=event_type,
        is_useful=is_useful,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/events/{event_id}",
    response_model=LyricsMemoryEventDetailResponse,
)
def lyrics_memory_event_detail(
    event_id: int,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> LyricsMemoryEventDetailResponse:
    return get_lyrics_memory_event(db, event_id)


@router.post(
    "/rules",
    response_model=LyricsMemoryEventDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def lyrics_memory_rule_create(
    request: Request,
    payload: LyricsMemoryManualRuleRequest,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> LyricsMemoryEventDetailResponse:
    result = create_lyrics_memory_rule(db, payload, admin.id)
    _audit(request, admin.id, "lyrics_memory_rule_created", [result.id])
    return result


@router.patch(
    "/events/{event_id}/usefulness",
    response_model=LyricsMemoryEventDetailResponse,
)
def lyrics_memory_event_usefulness(
    request: Request,
    event_id: int,
    payload: LyricsMemoryUsefulnessRequest,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> LyricsMemoryEventDetailResponse:
    result = set_lyrics_memory_event_usefulness(db, event_id, payload.is_useful)
    _audit(
        request,
        admin.id,
        "lyrics_memory_usefulness_updated",
        [event_id],
        is_useful=payload.is_useful,
    )
    return result


@router.delete("/events", response_model=LyricsMemoryDeleteResponse)
def lyrics_memory_bulk_delete(
    request: Request,
    payload: LyricsMemoryBulkDeleteRequest,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> LyricsMemoryDeleteResponse:
    result = delete_lyrics_memory_events(db, payload.event_ids)
    _audit(request, admin.id, "lyrics_memory_deleted", result.deleted_event_ids)
    return result


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def lyrics_memory_delete(
    request: Request,
    event_id: int,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> Response:
    delete_lyrics_memory_event(db, event_id)
    _audit(request, admin.id, "lyrics_memory_deleted", [event_id])
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _audit(
    request: Request,
    user_id: int,
    event: str,
    event_ids: list[int],
    **extra,
) -> None:
    audit_logger.info(
        event,
        extra={
            "request_id": get_request_id(request),
            "user_id": user_id,
            "lyrics_memory_event_ids": event_ids,
            **extra,
        },
    )
