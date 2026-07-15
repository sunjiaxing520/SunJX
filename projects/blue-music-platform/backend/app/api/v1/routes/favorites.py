import logging

from fastapi import APIRouter, Query, Request, status

from app.api.dependencies import CurrentUser, DatabaseSession
from app.core.logging import LOGGER_NAME
from app.core.request_context import get_request_id
from app.schemas.favorite import (
    FavoriteCreateRequest,
    FavoriteItemResponse,
    FavoriteItemType,
    FavoriteListResponse,
    FavoriteNoteUpdate,
)
from app.services.favorites import (
    create_favorite,
    delete_favorite,
    list_favorites,
    update_favorite_note,
)


router = APIRouter(prefix="/favorites")
audit_logger = logging.getLogger(f"{LOGGER_NAME}.audit")


@router.get("", response_model=FavoriteListResponse)
def favorite_history(
    db: DatabaseSession,
    user: CurrentUser,
    item_type: FavoriteItemType | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=100),
) -> FavoriteListResponse:
    return list_favorites(db, item_type, limit)


@router.post(
    "",
    response_model=FavoriteItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_favorite(
    request: Request,
    payload: FavoriteCreateRequest,
    db: DatabaseSession,
    user: CurrentUser,
) -> FavoriteItemResponse:
    favorite = create_favorite(db, payload, user.id)
    _audit(request, user.id, "favorite_created", favorite.id, favorite.item_type)
    return favorite


@router.patch("/{favorite_id}", response_model=FavoriteItemResponse)
def edit_favorite_note(
    request: Request,
    favorite_id: int,
    payload: FavoriteNoteUpdate,
    db: DatabaseSession,
    user: CurrentUser,
) -> FavoriteItemResponse:
    favorite = update_favorite_note(db, favorite_id, payload)
    _audit(request, user.id, "favorite_note_updated", favorite.id, favorite.item_type)
    return favorite


@router.delete("/{favorite_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    request: Request,
    favorite_id: int,
    db: DatabaseSession,
    user: CurrentUser,
) -> None:
    delete_favorite(db, favorite_id)
    _audit(request, user.id, "favorite_removed", favorite_id)


def _audit(
    request: Request,
    user_id: int,
    event: str,
    favorite_id: int,
    item_type: str | None = None,
) -> None:
    audit_logger.info(
        event,
        extra={
            "request_id": get_request_id(request),
            "user_id": user_id,
            "favorite_id": favorite_id,
            "favorite_type": item_type,
        },
    )
