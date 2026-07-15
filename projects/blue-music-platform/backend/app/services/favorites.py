from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppException
from app.models import (
    AnalysisReport,
    ApiUsageRecord,
    FavoriteItem,
    LyricsVersion,
)
from app.schemas.favorite import (
    FavoriteCreateRequest,
    FavoriteItemResponse,
    FavoriteItemType,
    FavoriteListResponse,
    FavoriteNoteUpdate,
)


def create_favorite(
    db: Session,
    payload: FavoriteCreateRequest,
    user_id: int,
) -> FavoriteItemResponse:
    _source_response_data(db, payload.item_type, payload.target_id)
    existing = _find_favorite(db, payload.item_type, payload.target_id)
    if existing is not None:
        return favorite_item_response(db, existing)

    favorite = FavoriteItem(
        item_type=payload.item_type,
        target_id=payload.target_id,
        created_by_id=user_id,
    )
    db.add(favorite)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = _find_favorite(db, payload.item_type, payload.target_id)
        if existing is None:
            raise
        return favorite_item_response(db, existing)
    db.refresh(favorite)
    return favorite_item_response(db, favorite)


def list_favorites(
    db: Session,
    item_type: FavoriteItemType | None = None,
    limit: int = 100,
) -> FavoriteListResponse:
    query = select(FavoriteItem).options(selectinload(FavoriteItem.creator))
    count_query = select(func.count(FavoriteItem.id))
    if item_type is not None:
        query = query.where(FavoriteItem.item_type == item_type)
        count_query = count_query.where(FavoriteItem.item_type == item_type)

    favorites = db.scalars(
        query.order_by(FavoriteItem.created_at.desc(), FavoriteItem.id.desc()).limit(limit)
    ).all()
    return FavoriteListResponse(
        items=[favorite_item_response(db, favorite) for favorite in favorites],
        total=db.scalar(count_query) or 0,
    )


def update_favorite_note(
    db: Session,
    favorite_id: int,
    payload: FavoriteNoteUpdate,
) -> FavoriteItemResponse:
    favorite = _get_favorite(db, favorite_id)
    favorite.note = payload.note
    db.commit()
    db.refresh(favorite)
    return favorite_item_response(db, favorite)


def delete_favorite(db: Session, favorite_id: int) -> None:
    favorite = _get_favorite(db, favorite_id)
    db.delete(favorite)
    db.commit()


def favorite_item_response(
    db: Session,
    favorite: FavoriteItem,
) -> FavoriteItemResponse:
    source = _source_response_data(db, favorite.item_type, favorite.target_id)
    return FavoriteItemResponse(
        id=favorite.id,
        item_type=favorite.item_type,
        target_id=favorite.target_id,
        source_task_id=source["source_task_id"],
        title=source["title"],
        summary=source["summary"],
        status=source["status"],
        provider=source["provider"],
        model=source["model"],
        total_tokens=_task_total_tokens(
            db, favorite.item_type, source["source_task_id"]
        ),
        source_created_at=source["source_created_at"],
        metadata=source["metadata"],
        note=favorite.note,
        created_by_id=favorite.created_by_id,
        created_by_username=favorite.creator.username if favorite.creator else None,
        favorited_at=favorite.created_at,
        updated_at=favorite.updated_at,
    )


def _source_response_data(
    db: Session,
    item_type: str,
    target_id: int,
) -> dict:
    if item_type == "analysis":
        report = db.scalar(
            select(AnalysisReport)
            .options(selectinload(AnalysisReport.task))
            .where(AnalysisReport.id == target_id)
        )
        if report is None:
            _raise_target_not_found(item_type, target_id)
        task = report.task
        return {
            "source_task_id": task.id,
            "title": f"榜单分析 #{task.id}",
            "summary": report.trend_summary,
            "status": task.status,
            "provider": task.provider,
            "model": task.model,
            "source_created_at": report.created_at,
            "metadata": {
                "window_start": task.window_start.isoformat(),
                "window_end": task.window_end.isoformat(),
                "selected_entry_count": report.trend_metrics.get("selected_count", 0),
                "direction_count": len(report.creation_directions),
            },
        }

    if item_type == "lyrics":
        version = db.scalar(
            select(LyricsVersion)
            .options(selectinload(LyricsVersion.task))
            .where(LyricsVersion.id == target_id)
        )
        if version is None:
            _raise_target_not_found(item_type, target_id)
        task = version.task
        return {
            "source_task_id": task.id,
            "title": version.title,
            "summary": task.theme,
            "status": task.status,
            "provider": task.provider,
            "model": task.model,
            "source_created_at": version.created_at,
            "metadata": {
                "version_number": version.version_number,
                "is_saved": version.is_saved,
                "language": task.language,
                "genre_tags": task.genre_tags,
                "mood_tags": task.mood_tags,
            },
        }

    raise AppException(
        code="FAVORITE_TYPE_INVALID",
        message="不支持的收藏类型",
        status_code=422,
        detail={"item_type": item_type},
    )


def _task_total_tokens(
    db: Session,
    item_type: str,
    task_id: int,
) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(ApiUsageRecord.total_tokens), 0)).where(
                ApiUsageRecord.task_type == item_type,
                ApiUsageRecord.task_id == task_id,
            )
        )
        or 0
    )


def _find_favorite(
    db: Session,
    item_type: str,
    target_id: int,
) -> FavoriteItem | None:
    return db.scalar(
        select(FavoriteItem)
        .options(selectinload(FavoriteItem.creator))
        .where(
            FavoriteItem.item_type == item_type,
            FavoriteItem.target_id == target_id,
        )
    )


def _get_favorite(db: Session, favorite_id: int) -> FavoriteItem:
    favorite = db.scalar(
        select(FavoriteItem)
        .options(selectinload(FavoriteItem.creator))
        .where(FavoriteItem.id == favorite_id)
    )
    if favorite is None:
        raise AppException(
            code="FAVORITE_NOT_FOUND",
            message="收藏记录不存在",
            status_code=404,
        )
    return favorite


def _raise_target_not_found(item_type: str, target_id: int) -> None:
    raise AppException(
        code="FAVORITE_TARGET_NOT_FOUND",
        message="要收藏的原始记录不存在",
        status_code=404,
        detail={"item_type": item_type, "target_id": target_id},
    )
