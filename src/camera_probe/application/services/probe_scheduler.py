from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

from camera_probe.application.services.probe_priority import ProbePriority

T = TypeVar("T")


@dataclass(slots=True)
class _Job:
    priority: ProbePriority
    sequence: int
    factory: Callable[[], Awaitable[object]]
    future: asyncio.Future[object]


class ProbeScheduler:
    """Bounded priority scheduler for health/discovery/manual work.

    Factories are used instead of already-created coroutines so cancellation
    while a job is queued cannot leak an un-awaited coroutine.
    """

    def __init__(self, concurrency: int = 16) -> None:
        self._concurrency = max(1, concurrency)
        self._queue: asyncio.PriorityQueue[tuple[int, int, _Job]] = asyncio.PriorityQueue()
        self._workers: list[asyncio.Task[None]] = []
        self._sequence = 0
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._workers = [
            asyncio.create_task(self._worker(), name=f"probe-scheduler-{i}")
            for i in range(self._concurrency)
        ]

    async def submit(
        self,
        operation: Callable[[], Awaitable[T]] | Awaitable[T],
        *,
        priority: ProbePriority = ProbePriority.DISCOVERY,
    ) -> T:
        """Submit work while preserving the legacy awaitable API.

        New code should pass a callable factory. Existing callers may still
        pass an Awaitable and remain source-compatible.
        """
        await self.start()
        loop = asyncio.get_running_loop()
        future: asyncio.Future[object] = loop.create_future()

        if callable(operation):
            factory: Callable[[], Awaitable[object]] = operation  # type: ignore[assignment]
        else:
            coroutine = operation
            consumed = False

            def factory() -> Awaitable[object]:
                nonlocal consumed
                if consumed:
                    raise RuntimeError("scheduled awaitable was already consumed")
                consumed = True
                return coroutine

        job = _Job(priority, self._sequence, factory, future)
        self._sequence += 1
        await self._queue.put((int(priority), job.sequence, job))

        try:
            return await future  # type: ignore[return-value]
        except asyncio.CancelledError:
            if not future.done():
                future.cancel()
            # If the operation is a legacy pre-created coroutine and remains
            # queued, close it because no worker will consume it.
            if not future.done() and not callable(operation):
                coroutine.close() if hasattr(coroutine, "close") else None  # type: ignore[attr-defined]
            raise

    async def _worker(self) -> None:
        while True:
            _, _, job = await self._queue.get()
            try:
                if job.future.cancelled():
                    continue
                try:
                    result = await job.factory()
                except asyncio.CancelledError:
                    if not job.future.done():
                        job.future.cancel()
                except Exception as exc:
                    if not job.future.done():
                        job.future.set_exception(exc)
                else:
                    if not job.future.done():
                        job.future.set_result(result)
            finally:
                self._queue.task_done()

    async def close(self) -> None:
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        while not self._queue.empty():
            _, _, job = self._queue.get_nowait()
            if not job.future.done():
                job.future.cancel()
            self._queue.task_done()
        self._workers.clear()
        self._started = False

    @property
    def queued(self) -> int:
        return self._queue.qsize()
