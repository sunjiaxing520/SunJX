from __future__ import annotations

import logging
import os
import socket
import time

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import LOGGER_NAME, configure_logging
from app.services.music import execute_music_task
from app.services.music_queue import (
    MusicQueueError,
    get_music_queue,
    recover_pending_music_tasks,
)
from app.services.task_recovery import recover_stale_music_tasks


logger = logging.getLogger(f"{LOGGER_NAME}.music_worker")


def run() -> None:
    configure_logging()
    queue = get_music_queue()
    queue.ping()
    recovered = queue.recover_processing()
    with SessionLocal() as db:
        stale = recover_stale_music_tasks(db)
    pending = recover_pending_music_tasks(queue)
    logger.info(
        "music_worker_started",
        extra={
            "worker_id": _worker_id(),
            "recovered_count": recovered,
            "stale_count": stale,
            "pending_count": pending,
        },
    )

    last_pending_scan = time.monotonic()
    while True:
        reservation = None
        lease = None
        try:
            queue.promote_due()
            if time.monotonic() - last_pending_scan >= 30:
                recover_pending_music_tasks(queue)
                last_pending_scan = time.monotonic()
            reservation = queue.reserve(settings.MUSIC_WORKER_RESERVE_SECONDS)
            if reservation is None:
                continue

            while lease is None:
                lease = queue.acquire_concurrency_slot()
                if lease is None:
                    time.sleep(1)
            queue.wait_for_rate_limit()
            outcome = execute_music_task(reservation.task_id)
            if outcome.retry_delay_seconds is not None:
                queue.schedule(
                    reservation.task_id,
                    outcome.retry_delay_seconds,
                )
        except MusicQueueError:
            logger.exception(
                "music_worker_queue_error",
                extra={"error_code": "MUSIC_QUEUE_REDIS_ERROR"},
            )
            time.sleep(5)
        except Exception:
            logger.exception(
                "music_worker_unexpected_error",
                extra={
                    "task_id": (
                        str(reservation.task_id) if reservation else None
                    ),
                    "error_code": "MUSIC_WORKER_UNEXPECTED_ERROR",
                },
            )
            time.sleep(2)
        finally:
            if lease is not None:
                try:
                    queue.release_concurrency_slot(lease)
                except MusicQueueError:
                    pass
            if reservation is not None:
                try:
                    queue.acknowledge(reservation)
                except MusicQueueError:
                    pass


def _worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


if __name__ == "__main__":
    run()
