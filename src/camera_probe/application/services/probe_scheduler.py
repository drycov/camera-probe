from __future__ import annotations

import asyncio
from dataclasses import dataclass

from camera_probe.application.services.probe_priority import ProbePriority


@dataclass(slots=True)
class _Job:
    priority: ProbePriority
    sequence: int
    coroutine: object
    future: asyncio.Future


class ProbeScheduler:
    """Bounded priority scheduler for health/discovery/manual work.

    Lower numeric priority wins. The scheduler owns a fixed number of workers,
    so callers cannot create an unbounded task storm. Within a priority level,
    jobs are FIFO.
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
        self._workers = [asyncio.create_task(self._worker(), name=f"probe-scheduler-{i}") for i in range(self._concurrency)]

    async def submit(self, coroutine, *, priority: ProbePriority = ProbePriority.DISCOVERY):
        await self.start()
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        sequence = self._sequence
        self._sequence += 1
        job = _Job(priority, sequence, coroutine, future)
        await self._queue.put((int(priority), sequence, job))
        try:
            return await future
        except asyncio.CancelledError:
            if not future.done():
                future.cancel()
            raise

    async def _worker(self) -> None:
        while True:
            _, _, job = await self._queue.get()
            try:
                if job.future.cancelled():
                    continue
                try:
                    result = await job.coroutine
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
        self._workers.clear()
        self._started = False

    @property
    def queued(self) -> int:
        return self._queue.qsize()
