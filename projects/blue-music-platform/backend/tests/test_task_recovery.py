from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import Base
from app.core.exceptions import AppException
from app.core.time import utc_now
from app.models import AnalysisTask, LyricsTask, TaskStatus
from app.schemas.analysis import AnalysisCreateRequest
from app.services.analysis import create_analysis
from app.services.lyrics import list_lyrics_tasks


def _lyrics_task(*, status: str, started_at, created_at) -> LyricsTask:
    return LyricsTask(
        status=status,
        provider="bigmodel",
        model="glm-4.7-flash",
        theme="测试任务恢复",
        language="中文",
        genre_tags=[],
        mood_tags=[],
        scene_tags=[],
        keywords=[],
        started_at=started_at,
        created_at=created_at,
    )


def test_listing_lyrics_recovers_only_tasks_past_runtime_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "AI_REQUEST_TIMEOUT_SECONDS", 5)
    monkeypatch.setattr(settings, "AI_MAX_RETRIES", 1)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    now = utc_now()

    with Session(engine) as db:
        stale_running = _lyrics_task(
            status=TaskStatus.RUNNING.value,
            started_at=now - timedelta(minutes=3),
            created_at=now - timedelta(minutes=3),
        )
        stale_pending = _lyrics_task(
            status=TaskStatus.PENDING.value,
            started_at=None,
            created_at=now - timedelta(minutes=3),
        )
        fresh_running = _lyrics_task(
            status=TaskStatus.RUNNING.value,
            started_at=now,
            created_at=now,
        )
        db.add_all([stale_running, stale_pending, fresh_running])
        db.commit()

        response = list_lyrics_tasks(db)
        tasks_by_id = {task.id: task for task in response.items}

        assert tasks_by_id[stale_running.id].status == TaskStatus.FAILED.value
        assert tasks_by_id[stale_running.id].error_code == "LYRICS_TASK_INTERRUPTED"
        assert tasks_by_id[stale_pending.id].status == TaskStatus.FAILED.value
        assert tasks_by_id[fresh_running.id].status == TaskStatus.RUNNING.value
        assert stale_running.completed_at is not None
        assert fresh_running.completed_at is None

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_analysis_rejects_a_second_active_task() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    now = utc_now()

    with Session(engine) as db:
        active = AnalysisTask(
            status=TaskStatus.RUNNING.value,
            provider="bigmodel",
            model="glm-4.7-flash",
            window_days=7,
            window_start=date.today() - timedelta(days=6),
            window_end=date.today(),
            started_at=now,
            created_at=now,
        )
        db.add(active)
        db.commit()

        with pytest.raises(AppException) as captured:
            create_analysis(
                db,
                AnalysisCreateRequest(entry_ids=[], window_days=7),
                user_id=1,
            )

        assert captured.value.code == "ANALYSIS_TASK_ALREADY_RUNNING"
        assert captured.value.status_code == 409
        assert captured.value.detail == {"active_task_id": active.id}

    Base.metadata.drop_all(bind=engine)
    engine.dispose()
