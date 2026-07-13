import logging
from datetime import date, timedelta

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.adapters.kugou import (
    KUGOU_CHART_CODE,
    KUGOU_CHART_NAME,
    KugouAdapterError,
    KugouRankingAdapter,
    RankingFetchResult,
    sample_ranking,
)
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import LOGGER_NAME
from app.core.time import app_today, utc_now
from app.models import CollectionTask, RankingEntry, RankingSnapshot, TaskStatus
from app.schemas.ranking import (
    CollectionCreateRequest,
    CollectionTaskResponse,
    RankingEntryPage,
    RankingEntryResponse,
    RankingSnapshotResponse,
)


task_logger = logging.getLogger(f"{LOGGER_NAME}.tasks")


def collection_task_response(task: CollectionTask) -> CollectionTaskResponse:
    return CollectionTaskResponse(
        id=task.id,
        platform=task.platform,
        chart_code=task.chart_code,
        chart_name=task.chart_name,
        source_mode=task.source_mode,
        snapshot_date=task.snapshot_date,
        status=task.status,
        snapshot_id=task.snapshot_id,
        item_count=task.item_count,
        error_code=task.error_code,
        error_message=task.error_message,
        started_at=task.started_at,
        completed_at=task.completed_at,
        created_at=task.created_at,
    )


def snapshot_response(snapshot: RankingSnapshot) -> RankingSnapshotResponse:
    return RankingSnapshotResponse(
        id=snapshot.id,
        platform=snapshot.platform,
        chart_code=snapshot.chart_code,
        chart_name=snapshot.chart_name,
        snapshot_date=snapshot.snapshot_date,
        source_updated_date=snapshot.source_updated_date,
        item_count=snapshot.item_count,
        collected_at=snapshot.collected_at,
    )


def entry_response(entry: RankingEntry) -> RankingEntryResponse:
    return RankingEntryResponse(
        id=entry.id,
        snapshot_id=entry.snapshot_id,
        source_song_id=entry.source_song_id,
        title=entry.title,
        artist=entry.artist,
        rank=entry.rank,
        popularity=entry.popularity,
        cover_url=entry.cover_url,
        source_url=entry.source_url,
        duration_seconds=entry.duration_seconds,
    )


def create_collection(
    db: Session,
    payload: CollectionCreateRequest,
    user_id: int,
) -> CollectionTaskResponse:
    today = app_today()
    snapshot_date = payload.snapshot_date or today
    if payload.source_mode == "live" and snapshot_date != today:
        raise AppException(
            code="CRAWLER_INVALID_SNAPSHOT_DATE",
            message="实时榜单只能保存为今天的快照",
            status_code=422,
        )
    if snapshot_date > today or snapshot_date < today - timedelta(days=29):
        raise AppException(
            code="CRAWLER_INVALID_SNAPSHOT_DATE",
            message="样例快照日期只能选择最近 30 天",
            status_code=422,
        )
    task = CollectionTask(
        platform="kugou",
        chart_code=KUGOU_CHART_CODE,
        chart_name=KUGOU_CHART_NAME,
        source_mode=payload.source_mode,
        snapshot_date=snapshot_date,
        status=TaskStatus.PENDING.value,
        requested_by_id=user_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    task.status = TaskStatus.RUNNING.value
    task.started_at = utc_now()
    db.commit()

    try:
        result = _fetch_ranking(payload)
        snapshot = _replace_daily_snapshot(db, snapshot_date, result)
        task.status = TaskStatus.COMPLETED.value
        task.snapshot_id = snapshot.id
        task.item_count = snapshot.item_count
        task.completed_at = utc_now()
        _delete_expired_rankings(db, today)
        db.commit()
        db.refresh(task)
        task_logger.info(
            "ranking_collection_completed",
            extra={"task_id": str(task.id), "item_count": task.item_count},
        )
        return collection_task_response(task)
    except KugouAdapterError as exc:
        db.rollback()
        _mark_collection_failed(db, task.id, "CRAWLER_SOURCE_UNAVAILABLE", str(exc))
        raise AppException(
            code="CRAWLER_SOURCE_UNAVAILABLE",
            message="酷狗榜单采集失败，请查看任务记录中的具体原因",
            status_code=502,
            detail={"task_id": task.id, "reason": str(exc)},
        ) from exc
    except Exception as exc:
        db.rollback()
        task_logger.exception(
            "ranking_collection_failed",
            extra={"task_id": str(task.id), "error_code": "CRAWLER_UNEXPECTED_ERROR"},
        )
        _mark_collection_failed(
            db,
            task.id,
            "CRAWLER_UNEXPECTED_ERROR",
            "采集流程发生未预期错误，请按任务编号检索日志",
        )
        raise AppException(
            code="CRAWLER_UNEXPECTED_ERROR",
            message="榜单采集失败，请稍后重试",
            status_code=500,
            detail={"task_id": task.id},
        ) from exc


def _fetch_ranking(payload: CollectionCreateRequest) -> RankingFetchResult:
    if payload.source_mode == "sample":
        return sample_ranking(payload.limit)
    return KugouRankingAdapter(
        timeout_seconds=settings.KUGOU_REQUEST_TIMEOUT_SECONDS,
        max_retries=settings.KUGOU_MAX_RETRIES,
    ).fetch(payload.limit)


def _replace_daily_snapshot(
    db: Session,
    snapshot_date: date,
    result: RankingFetchResult,
) -> RankingSnapshot:
    snapshot = db.scalar(
        select(RankingSnapshot).where(
            RankingSnapshot.platform == "kugou",
            RankingSnapshot.chart_code == result.chart_code,
            RankingSnapshot.snapshot_date == snapshot_date,
        )
    )
    if snapshot is None:
        snapshot = RankingSnapshot(
            platform="kugou",
            chart_code=result.chart_code,
            chart_name=result.chart_name,
            snapshot_date=snapshot_date,
        )
        db.add(snapshot)
        db.flush()
    else:
        db.execute(delete(RankingEntry).where(RankingEntry.snapshot_id == snapshot.id))

    snapshot.chart_name = result.chart_name
    snapshot.source_updated_date = result.source_updated_date
    snapshot.item_count = len(result.items)
    snapshot.collected_at = utc_now()
    db.add_all(
        RankingEntry(
            snapshot_id=snapshot.id,
            source_song_id=item.source_song_id,
            title=item.title,
            artist=item.artist,
            rank=item.rank,
            popularity=item.popularity,
            cover_url=item.cover_url,
            source_url=item.source_url,
            duration_seconds=item.duration_seconds,
            raw_data=item.raw_data,
        )
        for item in result.items
    )
    db.flush()
    return snapshot


def _delete_expired_rankings(db: Session, reference_date: date) -> None:
    cutoff = reference_date - timedelta(days=max(1, settings.RANKING_RETENTION_DAYS) - 1)
    expired_snapshot_ids = select(RankingSnapshot.id).where(
        RankingSnapshot.snapshot_date < cutoff
    )
    db.execute(
        delete(CollectionTask).where(CollectionTask.snapshot_date < cutoff)
    )
    db.execute(
        delete(RankingSnapshot).where(RankingSnapshot.id.in_(expired_snapshot_ids))
    )


def _mark_collection_failed(
    db: Session,
    task_id: int,
    code: str,
    message: str,
) -> None:
    task = db.get(CollectionTask, task_id)
    if task is None:
        return
    task.status = TaskStatus.FAILED.value
    task.error_code = code
    task.error_message = message
    task.completed_at = utc_now()
    db.commit()


def list_collection_tasks(db: Session, limit: int = 15) -> list[CollectionTaskResponse]:
    tasks = db.scalars(
        select(CollectionTask)
        .order_by(CollectionTask.created_at.desc(), CollectionTask.id.desc())
        .limit(limit)
    ).all()
    return [collection_task_response(task) for task in tasks]


def list_snapshots(db: Session, limit: int = 15) -> list[RankingSnapshotResponse]:
    snapshots = db.scalars(
        select(RankingSnapshot)
        .order_by(RankingSnapshot.snapshot_date.desc(), RankingSnapshot.id.desc())
        .limit(limit)
    ).all()
    return [snapshot_response(snapshot) for snapshot in snapshots]


def list_ranking_entries(
    db: Session,
    snapshot_id: int | None,
    page: int,
    page_size: int,
    search: str | None,
) -> RankingEntryPage:
    if snapshot_id is None:
        snapshot_id = db.scalar(
            select(RankingSnapshot.id)
            .order_by(RankingSnapshot.snapshot_date.desc(), RankingSnapshot.id.desc())
            .limit(1)
        )
    if snapshot_id is None:
        return RankingEntryPage(items=[], total=0, page=page, page_size=page_size)

    filters = [RankingEntry.snapshot_id == snapshot_id]
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(RankingEntry.title.ilike(pattern), RankingEntry.artist.ilike(pattern))
        )
    total = db.scalar(select(func.count(RankingEntry.id)).where(*filters)) or 0
    entries = db.scalars(
        select(RankingEntry)
        .where(*filters)
        .order_by(RankingEntry.rank)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return RankingEntryPage(
        items=[entry_response(entry) for entry in entries],
        total=total,
        page=page,
        page_size=page_size,
    )
