from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import LyricsMemoryEvent, LyricsTask, LyricsVersion
from app.services.lyrics_memory import (
    build_lyrics_skill_context,
    capture_accepted_result,
    capture_creation_request,
    capture_modification_request,
)


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


def test_lyrics_memory_keeps_context_filters_noise_and_builds_five_sections() -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        task = _task()
        db.add(task)
        db.flush()
        capture_creation_request(db, task, None)

        original = LyricsVersion(
            task_id=task.id,
            version_number=1,
            title="向远方",
            content="[Verse 1]\n旧句\n\n[Chorus1]\n向远方",
            style_prompt="流行, 励志",
            sections=[],
        )
        db.add(original)
        db.flush()
        capture_modification_request(
            db,
            task,
            original,
            "副歌更有力量\n副歌更有力量",
            None,
            message_id=12,
        )
        capture_modification_request(
            db,
            task,
            original,
            "谢谢",
            None,
            message_id=13,
        )

        accepted = LyricsVersion(
            task_id=task.id,
            version_number=2,
            title="向远方",
            content="[Verse 1]\n迎着光\n\n[Chorus1]\n向远方",
            style_prompt="流行, 励志",
            sections=[],
            is_saved=True,
        )
        db.add(accepted)
        db.flush()
        capture_accepted_result(
            db,
            task,
            accepted,
            None,
            instruction="副歌更有力量",
            source_version=original,
        )
        capture_accepted_result(db, task, accepted, None)
        db.commit()

        memory = build_lyrics_skill_context(db, current_task_id=task.id)
        event_count = db.scalar(select(func.count(LyricsMemoryEvent.id)))

        assert event_count == 4
        assert memory["skill_name"] == "lyrics_creation_distillation_v1"
        assert len(memory["1_true_creation_requirements"]) == 1
        assert memory["2_true_modification_requirements"] == [
            {"task_id": task.id, "request": "副歌更有力量"}
        ]
        assert memory["3_requirement_context"][0]["task_id"] == task.id
        assert memory["4_creation_distillation_expert"]["accepted_evidence"][0][
            "user_request"
        ] == "副歌更有力量"
        assert memory["5_ranking_lyrics_patterns"]["available"] is False
        assert "禁止" in memory["5_ranking_lyrics_patterns"]["status"]

    Base.metadata.drop_all(bind=engine)
    engine.dispose()
