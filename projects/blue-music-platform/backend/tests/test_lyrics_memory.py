from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import LyricsTask, LyricsTeamMemory, LyricsVersion
from app.schemas.lyrics_memory import LyricsMemorySettingsRequest
from app.services.lyrics_memory import (
    build_lyrics_skill_context,
    commit_lyrics_version_memory,
    update_lyrics_memory_settings,
)


def _insight(label: str) -> dict[str, object]:
    return {
        "requirement_summary": f"副歌需要简短直接，并强化{label}记忆点",
        "strategy_summary": f"用主歌推进{label}叙事，副歌集中释放情绪",
        "result_summary": f"完整结构能够承载{label}主题并保持可唱性",
        "reusable_patterns": [f"围绕{label}意象形成递进表达"],
        "highlight_summary": f"用一句简洁核心句凝聚{label}主题",
    }


def _task() -> LyricsTask:
    return LyricsTask(
        status="completed",
        provider="local",
        model="rules-v1",
        theme="成长",
        language="中文",
        genre_tags=["流行"],
        mood_tags=["励志"],
        scene_tags=["通勤"],
        keywords=["远方", "勇气"],
        requirements="副歌要直接、有记忆点",
        reference_text=None,
    )


def _version(task_id: int, number: int, label: str) -> LyricsVersion:
    return LyricsVersion(
        task_id=task_id,
        version_number=number,
        title=f"向{label}",
        content="[Verse 1]\n继续向前\n\n[Chorus1]\n继续向前",
        style_prompt="流行, 励志",
        sections=[],
        memory_insight=_insight(label),
        is_saved=False,
    )


def _engine():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


def test_memory_is_written_only_after_confirmation_and_only_once() -> None:
    engine = _engine()
    with Session(engine) as db:
        task = _task()
        db.add(task)
        db.flush()
        version = _version(task.id, 1, "远方")
        db.add(version)
        db.commit()

        before = build_lyrics_skill_context(db)
        assert before["items"] == []
        assert before["injection_limit"] == 60

        assert commit_lyrics_version_memory(db, version, None) is True
        db.commit()
        assert commit_lyrics_version_memory(db, version, None) is False
        db.commit()

        memory = db.scalar(select(LyricsTeamMemory))
        assert memory is not None
        assert memory.source_count == 1
        assert len(memory.items) == 5
        assert version.memory_committed_at is not None
    engine.dispose()


def test_similar_confirmed_experience_is_merged_and_moved_forward() -> None:
    engine = _engine()
    with Session(engine) as db:
        task = _task()
        db.add(task)
        db.flush()
        first = _version(task.id, 1, "远方")
        second = _version(task.id, 2, "远方")
        db.add_all([first, second])
        db.commit()

        commit_lyrics_version_memory(db, first, 1)
        commit_lyrics_version_memory(db, second, 2)
        db.commit()

        memory = db.scalar(select(LyricsTeamMemory))
        assert memory is not None
        assert memory.source_count == 2
        assert len(memory.items) == 5
        assert all(item["evidence_count"] == 2 for item in memory.items)
        assert memory.updated_by_id == 2
    engine.dispose()


def test_configured_injection_limit_controls_prompt_not_stored_memory() -> None:
    engine = _engine()
    with Session(engine) as db:
        task = _task()
        db.add(task)
        db.flush()
        for number, label in enumerate(("远方", "星河", "晨光"), start=1):
            version = _version(task.id, number, label)
            db.add(version)
            db.flush()
            commit_lyrics_version_memory(db, version, 1)
        db.commit()

        response = update_lyrics_memory_settings(
            db,
            LyricsMemorySettingsRequest(injection_limit=3),
            1,
        )
        context = build_lyrics_skill_context(db)
        assert response.total_items > 3
        assert response.injection_limit == 3
        assert context["total_memory_items"] == response.total_items
        assert len(context["items"]) == 3
    engine.dispose()
