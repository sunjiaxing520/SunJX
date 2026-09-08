"""Exercise real PostgreSQL admission locks and Redis without provider calls."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base
from app.models import MusicTask
from app.services.music import _claim_music_task, _get_or_create_music_settings
from app.services.music_queue import RedisMusicQueue


def main():
    suffix = uuid4().hex
    database = f"blue_music_probe_{suffix}"
    admin = create_engine(settings.DATABASE_URL, isolation_level="AUTOCOMMIT")
    probe = None
    queue = None
    created = False
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database}"'))
        created = True
        probe = create_engine(make_url(settings.DATABASE_URL).set(database=database))
        Base.metadata.create_all(probe)
        sessions = sessionmaker(probe, autoflush=False)
        settings.MUSIC_MAX_CONCURRENCY = 1
        with sessions() as db:
            _get_or_create_music_settings(db)
            tasks = [MusicTask(
                title="Probe", lyrics="Probe", style_prompt="pop", negative_tags=[],
                provider_implementation="sunoapi_org",
            ) for _ in range(2)]
            db.add_all(tasks)
            db.commit()
            task_ids = [task.id for task in tasks]

        barrier = Barrier(2)

        def claim(task_id):
            with sessions() as db:
                db.execute(text("SET lock_timeout = '5s'"))
                task = db.get(MusicTask, task_id)
                barrier.wait(timeout=10)
                outcome = _claim_music_task(db, task)
                return "claimed" if outcome is None else outcome.status

        with ThreadPoolExecutor(max_workers=2) as workers:
            outcomes = list(workers.map(claim, task_ids))
        assert sorted(outcomes) == ["claimed", "waiting_capacity"], outcomes
        with sessions() as db:
            for task in db.query(MusicTask).all():
                task.status = "pending"
                task.external_task_id = "probe-existing-job"
                task.next_attempt_at = None
            db.commit()
        with ThreadPoolExecutor(max_workers=2) as workers:
            outcomes = list(workers.map(claim, [task_ids[0], task_ids[0]]))
        assert sorted(outcomes) == ["claimed", "ignored"], outcomes

        settings.MUSIC_QUEUE_NAME = f"blue_music:probe:{suffix}"
        queue = RedisMusicQueue()
        assert queue.enqueue(1)
        assert not queue.enqueue(1)
        reservation = queue.reserve(1)
        assert reservation.task_id == 1
        queue.acknowledge(reservation)
        lease = queue.acquire_concurrency_slot()
        assert lease is not None
        assert queue.acquire_concurrency_slot() is None
        queue.release_concurrency_slot(lease)
        queue.schedule(2, 0)
        assert queue.promote_due() == 1
        reservation = queue.reserve(1)
        assert reservation.task_id == 2
        queue.acknowledge(reservation)
    finally:
        if queue is not None:
            keys = list(queue.client.scan_iter(match=f"{queue.queue_key}*"))
            if keys:
                queue.client.delete(*keys)
            queue.client.close()
        if probe is not None:
            probe.dispose()
        if created:
            with admin.connect() as connection:
                connection.execute(text(f'DROP DATABASE "{database}"'))
        admin.dispose()
    print(json.dumps({"postgres_admission": "passed", "atomic_claim": "passed",
                      "redis_queue": "passed", "isolated_resources_removed": True}))


if __name__ == "__main__":
    main()
