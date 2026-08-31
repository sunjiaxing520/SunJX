import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.adapters.text_generation import LocalTextProvider
from app.core.database import Base
from app.models import LyricsMemoryEvent, LyricsTask, LyricsVersion
from app.services import lyrics_memory
from app.services.lyrics_memory import (
    build_lyrics_skill_context,
    capture_accepted_result,
    capture_creation_request,
    capture_modification_request,
    distill_next_legacy_lyrics_memory,
)


def _insight(label: str) -> dict[str, object]:
    return {
        "requirement_summary": f"提炼后的{label}需求摘要",
        "strategy_summary": f"提炼后的{label}创作与修改方法",
        "result_summary": f"提炼后的{label}有效结果",
        "reusable_patterns": [f"可复用的{label}表达方法"],
        "highlight_summary": f"提炼后的{label}亮点总结",
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
            memory_insight=_insight("首次创作"),
            is_saved=True,
        )
        db.add(original)
        db.flush()
        capture_accepted_result(db, task, original, None)
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
            memory_insight=_insight("确认修改"),
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
        db.commit()

        memory = build_lyrics_skill_context(db, current_task_id=task.id)
        event_count = db.scalar(select(func.count(LyricsMemoryEvent.id)))

        assert event_count == 5
        assert memory["skill_name"] == "lyrics_creation_distillation_v1"
        assert len(memory["1_true_creation_requirements"]) == 1
        assert memory["2_true_modification_requirements"] == [
            {
                "task_id": task.id,
                "requirement_summary": "提炼后的确认修改需求摘要",
                "strategy_summary": "提炼后的确认修改创作与修改方法",
                "result_summary": "提炼后的确认修改有效结果",
            }
        ]
        assert memory["3_requirement_context"][0]["task_id"] == task.id
        assert memory["4_creation_distillation_expert"]["accepted_evidence"][0][
            "result_summary"
        ] == "提炼后的确认修改有效结果"
        serialized_memory = str(memory)
        assert "副歌更有力量" not in serialized_memory
        assert "旧句" not in serialized_memory
        assert "迎着光" not in serialized_memory
        assert memory["5_ranking_lyrics_patterns"]["available"] is False
        assert "禁止" in memory["5_ranking_lyrics_patterns"]["status"]

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_legacy_accepted_result_is_distilled_and_raw_context_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(
        lyrics_memory,
        "resolve_text_provider",
        lambda _db: LocalTextProvider(),
    )
    with Session(engine) as db:
        task = _task()
        db.add(task)
        db.flush()
        version = LyricsVersion(
            task_id=task.id,
            version_number=1,
            title="向远方",
            content="[Verse 1]\n旧歌词\n\n[Chorus1]\n向远方",
            style_prompt="流行, 励志",
            sections=[],
            memory_insight=None,
            is_saved=True,
        )
        db.add(version)
        db.flush()
        event = LyricsMemoryEvent(
            event_type="accepted_result",
            task_id=task.id,
            source_version_id=version.id,
            created_by_id=None,
            dedupe_key=f"accepted-version:{version.id}",
            raw_content="用户将该版本设为当前作品",
            cleaned_content="用户将该版本设为当前作品",
            context_data={
                "title": version.title,
                "theme": task.theme,
                "user_request": "副歌更有力量",
                "before_lyrics": "旧句",
                "accepted_lyrics": version.content,
                "accepted_style_prompt": version.style_prompt,
            },
            is_useful=True,
        )
        db.add(event)
        db.commit()

        result = distill_next_legacy_lyrics_memory(db)
        db.refresh(event)
        db.refresh(version)

        assert result.processed_count == 1
        assert result.pending_legacy_count == 0
        assert version.memory_insight is not None
        assert event.context_data["memory_insight"] == version.memory_insight
        assert "accepted_lyrics" not in event.context_data
        assert "before_lyrics" not in event.context_data
        memory = build_lyrics_skill_context(db)
        serialized_memory = str(memory)
        assert "副歌更有力量" not in serialized_memory
        assert "旧歌词" not in serialized_memory

    Base.metadata.drop_all(bind=engine)
    engine.dispose()
