from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol


class JobQueue(Protocol):
    def enqueue(self, task_name: str, payload: dict[str, str]) -> str: ...


@dataclass
class InMemoryJobQueue:
    jobs: list[tuple[str, dict[str, str], str]] = field(default_factory=list)

    def enqueue(self, task_name: str, payload: dict[str, str]) -> str:
        job_id = str(uuid.uuid4())
        self.jobs.append((task_name, payload, job_id))
        return job_id


@dataclass
class RQJobQueue:
    redis_url: str
    queue_name: str = "invoices"

    def enqueue(self, task_name: str, payload: dict[str, str]) -> str:
        try:
            from redis import Redis  # type: ignore[import-untyped]
            from rq import Queue  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("rq/redis are required for RQJobQueue") from exc

        queue = Queue(name=self.queue_name, connection=Redis.from_url(self.redis_url))
        job = queue.enqueue(task_name, payload)
        return str(job.id)


def build_queue(redis_url: str | None = None) -> JobQueue:
    if redis_url:
        return RQJobQueue(redis_url=redis_url)
    return InMemoryJobQueue()


def drain_in_memory_queue(
    queue: InMemoryJobQueue,
    handlers: dict[str, Callable[[dict[str, str]], None]],
) -> int:
    processed = 0
    while queue.jobs:
        task_name, payload, _job_id = queue.jobs.pop(0)
        handler = handlers[task_name]
        handler(payload)
        processed += 1
    return processed
