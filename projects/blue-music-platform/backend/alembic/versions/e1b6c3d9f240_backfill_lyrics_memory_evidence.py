"""backfill lyrics memory evidence

Revision ID: e1b6c3d9f240
Revises: d8a4f1c7e920
Create Date: 2026-08-31

"""
from typing import Sequence, Union

from alembic import op


revision: str = "e1b6c3d9f240"
down_revision: Union[str, None] = "d8a4f1c7e920"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO lyrics_memory_events (
            event_type,
            task_id,
            source_version_id,
            created_by_id,
            dedupe_key,
            raw_content,
            cleaned_content,
            context,
            is_useful,
            created_at
        )
        SELECT
            'creation_request',
            task.id,
            NULL,
            task.requested_by_id,
            'creation-task:' || task.id,
            concat_ws(
                E'\n',
                CASE WHEN task.title_hint IS NOT NULL AND task.title_hint <> ''
                    THEN '歌名：' || task.title_hint END,
                '主题：' || task.theme,
                CASE WHEN task.requirements IS NOT NULL AND task.requirements <> ''
                    THEN '补充要求：' || task.requirements END,
                CASE WHEN task.reference_text IS NOT NULL AND task.reference_text <> ''
                    THEN '参考文本：' || task.reference_text END
            ),
            concat_ws(
                E'\n',
                CASE WHEN task.title_hint IS NOT NULL AND task.title_hint <> ''
                    THEN '歌名：' || task.title_hint END,
                '主题：' || task.theme,
                CASE WHEN task.requirements IS NOT NULL AND task.requirements <> ''
                    THEN '补充要求：' || task.requirements END,
                CASE WHEN task.reference_text IS NOT NULL AND task.reference_text <> ''
                    THEN '参考文本：' || task.reference_text END
            ),
            json_build_object(
                'analysis_report_id', task.analysis_report_id,
                'direction_index', task.direction_index,
                'title', task.title_hint,
                'theme', task.theme,
                'genre_tags', task.genre_tags,
                'mood_tags', task.mood_tags,
                'scene_tags', task.scene_tags,
                'keywords', task.keywords
            ),
            CASE
                WHEN lower(btrim(task.theme)) IN ('test', '测试', '试一下', '随便')
                    AND coalesce(btrim(task.requirements), '') = ''
                    AND coalesce(btrim(task.reference_text), '') = ''
                THEN false
                ELSE true
            END,
            task.created_at
        FROM lyrics_tasks AS task
        ON CONFLICT (dedupe_key) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO lyrics_memory_events (
            event_type,
            task_id,
            source_version_id,
            created_by_id,
            dedupe_key,
            raw_content,
            cleaned_content,
            context,
            is_useful,
            created_at
        )
        SELECT
            'modification_request',
            message.task_id,
            message.source_version_id,
            message.created_by_id,
            'modification-message:' || message.id,
            message.content,
            btrim(message.content),
            json_build_object(
                'source_title', version.title,
                'source_lyrics', version.content,
                'theme', task.theme,
                'requirements', task.requirements,
                'review_run_id', message.review_run_id
            ),
            CASE
                WHEN lower(btrim(message.content)) IN (
                    'test', '你好', '您好', '好的', '好', '谢谢',
                    '测试', '试一下', '随便', '继续', '没了'
                ) THEN false
                ELSE true
            END,
            message.created_at
        FROM lyrics_assistant_messages AS message
        JOIN lyrics_tasks AS task ON task.id = message.task_id
        JOIN lyrics_versions AS version ON version.id = message.source_version_id
        WHERE message.role = 'user'
        ON CONFLICT (dedupe_key) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO lyrics_memory_events (
            event_type,
            task_id,
            source_version_id,
            created_by_id,
            dedupe_key,
            raw_content,
            cleaned_content,
            context,
            is_useful,
            created_at
        )
        SELECT
            'accepted_result',
            version.task_id,
            version.id,
            task.requested_by_id,
            'accepted-version:' || version.id,
            '历史中已保存为当前作品',
            '历史中已保存为当前作品',
            json_build_object(
                'title', version.title,
                'theme', task.theme,
                'user_request', NULL,
                'before_lyrics', NULL,
                'accepted_lyrics', version.content,
                'accepted_style_prompt', version.style_prompt
            ),
            true,
            version.created_at
        FROM lyrics_versions AS version
        JOIN lyrics_tasks AS task ON task.id = version.task_id
        WHERE version.is_saved = true
        ON CONFLICT (dedupe_key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM lyrics_memory_events
        WHERE dedupe_key LIKE 'creation-task:%'
           OR dedupe_key LIKE 'modification-message:%'
           OR dedupe_key LIKE 'accepted-version:%'
        """
    )
