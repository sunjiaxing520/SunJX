import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.adapters.text_generation import TextProviderError
from app.core.exceptions import AppException
from app.core.logging import LOGGER_NAME
from app.models import (
    AnalysisReport,
    AnalysisTask,
    AnalysisTaskEntry,
    RankingEntry,
    RankingSnapshot,
    TaskStatus,
)
from app.schemas.analysis import (
    AnalysisCreateRequest,
    AnalysisReportResponse,
    AnalysisTaskListResponse,
    AnalysisTaskResponse,
)
from app.services.api_usage import record_api_usage, task_api_usage
from app.services.ai_providers import resolve_text_provider
from app.services.task_recovery import recover_stale_text_tasks


task_logger = logging.getLogger(f"{LOGGER_NAME}.tasks")


def analysis_task_response(db: Session, task: AnalysisTask) -> AnalysisTaskResponse:
    report = None
    if task.report is not None:
        report = AnalysisReportResponse(
            id=task.report.id,
            task_id=task.report.task_id,
            trend_summary=task.report.trend_summary,
            trend_metrics=task.report.trend_metrics,
            creation_directions=task.report.creation_directions,
            evidence=task.report.evidence,
            created_at=task.report.created_at,
        )
    return AnalysisTaskResponse(
        id=task.id,
        status=task.status,
        provider=task.provider,
        model=task.model,
        window_days=task.window_days,
        window_start=task.window_start,
        window_end=task.window_end,
        selected_entry_count=len(task.selected_entries),
        error_code=task.error_code,
        error_message=task.error_message,
        started_at=task.started_at,
        completed_at=task.completed_at,
        created_at=task.created_at,
        api_usage=task_api_usage(db, "analysis", task.id),
        report=report,
    )


def create_analysis(
    db: Session,
    payload: AnalysisCreateRequest,
    user_id: int,
) -> AnalysisTaskResponse:
    selected_entries = _resolve_selected_entries(db, payload.entry_ids)
    latest_snapshot = db.get(RankingSnapshot, selected_entries[0].snapshot_id)
    if latest_snapshot is None:
        raise AppException(
            code="ANALYSIS_SNAPSHOT_NOT_FOUND",
            message="所选榜单快照不存在",
            status_code=404,
        )
    if any(entry.snapshot_id != latest_snapshot.id for entry in selected_entries):
        raise AppException(
            code="ANALYSIS_MIXED_SNAPSHOTS",
            message="一次分析只能选择同一个榜单日期的歌曲",
            status_code=422,
        )

    window_end = latest_snapshot.snapshot_date
    window_start = window_end - timedelta(days=payload.window_days - 1)
    try:
        provider = resolve_text_provider(db)
    except TextProviderError as exc:
        raise AppException(
            code="AI_PROVIDER_RUNTIME_INVALID",
            message="当前 AI 接口配置不可用，请联系超级管理员检查接口设置",
            status_code=503,
            detail={"reason": str(exc)},
        ) from exc
    task = AnalysisTask(
        status=TaskStatus.PENDING.value,
        provider=provider.name,
        model=provider.model,
        window_days=payload.window_days,
        window_start=window_start,
        window_end=window_end,
        requested_by_id=user_id,
        selected_entries=[
            AnalysisTaskEntry(entry_id=entry.id) for entry in selected_entries
        ],
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    task.status = TaskStatus.RUNNING.value
    task.started_at = datetime.now(timezone.utc)
    db.commit()

    try:
        context, metrics, evidence = _build_analysis_context(
            db, selected_entries, window_start, window_end
        )
        generated_result = provider.analyze(context)
        generated = generated_result.output
        report = AnalysisReport(
            task_id=task.id,
            trend_summary=generated.trend_summary,
            trend_metrics=metrics,
            creation_directions=[
                direction.model_dump() for direction in generated.creation_directions
            ],
            evidence=evidence,
            provider_payload=generated.model_dump(),
        )
        db.add(report)
        record_api_usage(
            db,
            task_type="analysis",
            task_id=task.id,
            operation="analysis.generate",
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
        _mark_analysis_failed(
            db,
            task.id,
            "ANALYSIS_PROVIDER_FAILED",
            str(exc),
            call=getattr(exc, "call", None),
        )
        raise AppException(
            code="ANALYSIS_PROVIDER_FAILED",
            message="榜单分析失败，请查看任务记录中的具体原因",
            status_code=502,
            detail={"task_id": task.id, "reason": str(exc)},
        ) from exc
    except Exception as exc:
        db.rollback()
        task_logger.exception(
            "analysis_task_failed",
            extra={"task_id": str(task.id), "error_code": "ANALYSIS_UNEXPECTED_ERROR"},
        )
        _mark_analysis_failed(
            db,
            task.id,
            "ANALYSIS_UNEXPECTED_ERROR",
            "分析流程发生未预期错误，请按任务编号检索日志",
        )
        raise AppException(
            code="ANALYSIS_UNEXPECTED_ERROR",
            message="榜单分析失败，请稍后重试",
            status_code=500,
            detail={"task_id": task.id},
        ) from exc

    return get_analysis_task(db, task.id)


def _resolve_selected_entries(db: Session, entry_ids: list[int]) -> list[RankingEntry]:
    if entry_ids:
        entries = list(
            db.scalars(
                select(RankingEntry)
                .where(RankingEntry.id.in_(set(entry_ids)))
                .order_by(RankingEntry.rank)
            ).all()
        )
        if len(entries) != len(set(entry_ids)):
            raise AppException(
                code="ANALYSIS_ENTRY_NOT_FOUND",
                message="部分所选歌曲不存在或已经过期",
                status_code=404,
            )
        return entries

    latest_snapshot_id = db.scalar(
        select(RankingSnapshot.id)
        .order_by(RankingSnapshot.snapshot_date.desc(), RankingSnapshot.id.desc())
        .limit(1)
    )
    if latest_snapshot_id is None:
        raise AppException(
            code="ANALYSIS_NO_RANKING_DATA",
            message="还没有榜单数据，请先运行榜单采集",
            status_code=409,
        )
    entries = list(
        db.scalars(
            select(RankingEntry)
            .where(RankingEntry.snapshot_id == latest_snapshot_id)
            .order_by(RankingEntry.rank)
            .limit(30)
        ).all()
    )
    if not entries:
        raise AppException(
            code="ANALYSIS_NO_RANKING_DATA",
            message="最新榜单没有可分析的歌曲",
            status_code=409,
        )
    return entries


def _build_analysis_context(
    db: Session,
    selected_entries: list[RankingEntry],
    window_start,
    window_end,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    source_ids = {entry.source_song_id for entry in selected_entries}
    history = list(
        db.execute(
            select(RankingEntry, RankingSnapshot.snapshot_date)
            .join(RankingSnapshot, RankingSnapshot.id == RankingEntry.snapshot_id)
            .where(
                RankingEntry.source_song_id.in_(source_ids),
                RankingSnapshot.snapshot_date >= window_start,
                RankingSnapshot.snapshot_date <= window_end,
            )
            .order_by(RankingSnapshot.snapshot_date, RankingEntry.rank)
        ).all()
    )
    available_dates = list(
        db.scalars(
            select(RankingSnapshot.snapshot_date)
            .where(
                RankingSnapshot.snapshot_date >= window_start,
                RankingSnapshot.snapshot_date <= window_end,
            )
            .distinct()
            .order_by(RankingSnapshot.snapshot_date)
        ).all()
    )
    by_song: dict[str, list[tuple[RankingEntry, object]]] = defaultdict(list)
    for entry, snapshot_date in history:
        by_song[entry.source_song_id].append((entry, snapshot_date))

    rising = falling = stable = new = 0
    songs: list[dict[str, object]] = []
    for selected in selected_entries:
        points = by_song[selected.source_song_id]
        movement = 0
        if len(points) >= 2:
            movement = points[0][0].rank - points[-1][0].rank
            if movement > 0:
                rising += 1
            elif movement < 0:
                falling += 1
            else:
                stable += 1
        elif len(available_dates) > 1:
            new += 1
        else:
            stable += 1
        songs.append(
            {
                "entry_id": selected.id,
                "source_song_id": selected.source_song_id,
                "title": selected.title,
                "artist": selected.artist,
                "latest_rank": selected.rank,
                "rank_movement": movement,
                "observed_days": len(points),
            }
        )

    metrics: dict[str, object] = {
        "selected_count": len(selected_entries),
        "available_days": len(available_dates),
        "rising_count": rising,
        "falling_count": falling,
        "stable_count": stable,
        "new_count": new,
        "top_rising": sorted(
            (song for song in songs if int(song["rank_movement"]) > 0),
            key=lambda song: int(song["rank_movement"]),
            reverse=True,
        )[:10],
    }
    confidence = "high" if len(available_dates) >= 7 else "medium" if len(available_dates) >= 3 else "low"
    evidence: dict[str, object] = {
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "snapshot_dates": [value.isoformat() for value in available_dates],
        "confidence": confidence,
        "limitations": [
            "仅使用榜单元数据和排名变化，未下载或分析音频",
            "曲风、情绪、乐器和人声为创作方向推断，不是歌曲事实标签",
            "不输出准确 BPM、调性、和弦或原曲复刻要求",
        ],
    }
    return {"songs": songs, "metrics": metrics, "evidence": evidence}, metrics, evidence


def _mark_analysis_failed(
    db: Session,
    task_id: int,
    code: str,
    message: str,
    *,
    call=None,
) -> None:
    task = db.get(AnalysisTask, task_id)
    if task is None:
        return
    task.status = TaskStatus.FAILED.value
    task.error_code = code
    task.error_message = message
    task.completed_at = datetime.now(timezone.utc)
    record_api_usage(
        db,
        task_type="analysis",
        task_id=task.id,
        operation="analysis.generate",
        provider=task.provider,
        model=task.model,
        call=call,
        status=TaskStatus.FAILED.value,
        error_code=code,
        error_message=message,
    )
    db.commit()


def get_analysis_task(db: Session, task_id: int) -> AnalysisTaskResponse:
    recover_stale_text_tasks(db)
    task = db.scalar(
        select(AnalysisTask)
        .options(
            selectinload(AnalysisTask.selected_entries),
            selectinload(AnalysisTask.report),
        )
        .where(AnalysisTask.id == task_id)
    )
    if task is None:
        raise AppException(
            code="ANALYSIS_TASK_NOT_FOUND",
            message="分析任务不存在",
            status_code=404,
        )
    return analysis_task_response(db, task)


def list_analysis_tasks(db: Session, limit: int = 15) -> AnalysisTaskListResponse:
    recover_stale_text_tasks(db)
    tasks = db.scalars(
        select(AnalysisTask)
        .options(
            selectinload(AnalysisTask.selected_entries),
            selectinload(AnalysisTask.report),
        )
        .order_by(AnalysisTask.created_at.desc(), AnalysisTask.id.desc())
        .limit(limit)
    ).all()
    total = db.scalar(select(func.count(AnalysisTask.id))) or 0
    return AnalysisTaskListResponse(
        items=[analysis_task_response(db, task) for task in tasks],
        total=total,
    )
