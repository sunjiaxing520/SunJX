from __future__ import annotations

import logging
import math
import time
import uuid
from dataclasses import dataclass

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import or_, select

from app.core.config import music_execution_timeout_seconds, settings
from app.core.database import SessionLocal
from app.core.logging import LOGGER_NAME
from app.core.time import utc_now
from app.models import MusicTask, TaskStatus


queue_logger = logging.getLogger(f"{LOGGER_NAME}.music_queue")


class MusicQueueError(RuntimeError):
    pass


@dataclass(frozen=True)
class MusicQueueReservation:
    task_id: int
    raw_value: str


@dataclass(frozen=True)
class MusicConcurrencyLease:
    slot: int
    token: str


class RedisMusicQueue:
    def __init__(self, client: Redis | None = None) -> None:
        self.client = client or Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=max(10, settings.MUSIC_WORKER_RESERVE_SECONDS + 5),
            health_check_interval=30,
        )
        self.queue_key = settings.MUSIC_QUEUE_NAME
        self.processing_key = f"{self.queue_key}:processing"
        self.delayed_key = f"{self.queue_key}:delayed"
        self.dedup_prefix = f"{self.queue_key}:dedup"
        self.rate_key = f"{self.queue_key}:rate"
        self.slot_prefix = f"{self.queue_key}:slot"

    def ping(self) -> None:
        try:
            self.client.ping()
        except RedisError as exc:
            raise MusicQueueError("无法连接 Redis 音乐任务队列") from exc

    def enqueue(self, task_id: int) -> bool:
        value = str(task_id)
        dedup_key = f"{self.dedup_prefix}:{task_id}"
        try:
            added = self.client.set(
                dedup_key,
                "1",
                nx=True,
                ex=max(3600, round(settings.SUNO_GENERATION_TIMEOUT_SECONDS * 2)),
            )
            if not added:
                return False
            try:
                self.client.lpush(self.queue_key, value)
            except RedisError:
                self.client.delete(dedup_key)
                raise
            return True
        except RedisError as exc:
            raise MusicQueueError("音乐任务写入 Redis 队列失败") from exc

    def schedule(self, task_id: int, delay_seconds: float) -> None:
        score = time.time() + max(0.0, delay_seconds)
        try:
            self.client.zadd(self.delayed_key, {str(task_id): score})
        except RedisError as exc:
            raise MusicQueueError("音乐任务写入延迟队列失败") from exc

    def promote_due(self, limit: int = 100) -> int:
        try:
            values = self.client.zrangebyscore(
                self.delayed_key,
                min="-inf",
                max=time.time(),
                start=0,
                num=limit,
            )
            promoted = 0
            for value in values:
                if self.client.zrem(self.delayed_key, value):
                    self.client.delete(f"{self.dedup_prefix}:{value}")
                    self.enqueue(int(value))
                    promoted += 1
            return promoted
        except (RedisError, ValueError) as exc:
            raise MusicQueueError("提升延迟音乐任务失败") from exc

    def reserve(self, timeout_seconds: int) -> MusicQueueReservation | None:
        try:
            value = self.client.brpoplpush(
                self.queue_key,
                self.processing_key,
                timeout=max(1, timeout_seconds),
            )
            if value is None:
                return None
            self.client.delete(f"{self.dedup_prefix}:{value}")
            return MusicQueueReservation(task_id=int(value), raw_value=value)
        except (RedisError, ValueError) as exc:
            raise MusicQueueError("读取 Redis 音乐任务队列失败") from exc

    def acknowledge(self, reservation: MusicQueueReservation) -> None:
        try:
            self.client.lrem(self.processing_key, 1, reservation.raw_value)
        except RedisError as exc:
            raise MusicQueueError("确认 Redis 音乐任务失败") from exc

    def recover_processing(self) -> int:
        recovered = 0
        try:
            while True:
                value = self.client.rpoplpush(
                    self.processing_key,
                    self.queue_key,
                )
                if value is None:
                    return recovered
                recovered += 1
        except RedisError as exc:
            raise MusicQueueError("恢复中断的 Redis 音乐任务失败") from exc

    def acquire_concurrency_slot(self) -> MusicConcurrencyLease | None:
        ttl_seconds = max(
            120,
            math.ceil(music_execution_timeout_seconds()),
        )
        try:
            for slot in range(max(1, settings.MUSIC_MAX_CONCURRENCY)):
                token = uuid.uuid4().hex
                acquired = self.client.set(
                    f"{self.slot_prefix}:{slot}",
                    token,
                    nx=True,
                    ex=ttl_seconds,
                )
                if acquired:
                    return MusicConcurrencyLease(slot=slot, token=token)
            return None
        except RedisError as exc:
            raise MusicQueueError("获取音乐任务并发槽失败") from exc

    def release_concurrency_slot(self, lease: MusicConcurrencyLease) -> None:
        script = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('del', KEYS[1])
        end
        return 0
        """
        try:
            self.client.eval(
                script,
                1,
                f"{self.slot_prefix}:{lease.slot}",
                lease.token,
            )
        except RedisError as exc:
            queue_logger.warning(
                "music_concurrency_lease_release_failed",
                extra={"error_code": "MUSIC_QUEUE_REDIS_ERROR"},
            )
            raise MusicQueueError("释放音乐任务并发槽失败") from exc

    def wait_for_rate_limit(self) -> None:
        interval = max(0.0, settings.MUSIC_MIN_REQUEST_INTERVAL_SECONDS)
        if interval <= 0:
            return
        ttl_ms = max(1, math.ceil(interval * 1000))
        while True:
            try:
                acquired = self.client.set(
                    self.rate_key,
                    uuid.uuid4().hex,
                    nx=True,
                    px=ttl_ms,
                )
                if acquired:
                    return
                remaining_ms = self.client.pttl(self.rate_key)
            except RedisError as exc:
                raise MusicQueueError("读取音乐接口限频状态失败") from exc
            time.sleep(max(0.1, min(interval, remaining_ms / 1000 if remaining_ms > 0 else 0.5)))


def get_music_queue() -> RedisMusicQueue:
    return RedisMusicQueue()


def recover_pending_music_tasks(queue: RedisMusicQueue) -> int:
    with SessionLocal() as db:
        task_ids = db.scalars(
            select(MusicTask.id).where(
                MusicTask.status == TaskStatus.PENDING.value,
                or_(
                    MusicTask.next_attempt_at.is_(None),
                    MusicTask.next_attempt_at <= utc_now(),
                ),
            )
        ).all()
    enqueued = 0
    for task_id in task_ids:
        if queue.enqueue(task_id):
            enqueued += 1
    return enqueued
