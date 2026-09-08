import asyncio

from camera_probe.application.services.probe_priority import ProbePriority
from camera_probe.application.services.probe_scheduler import ProbeScheduler


def test_queued_factory_is_not_started_after_cancellation() -> None:
    async def run() -> None:
        scheduler = ProbeScheduler(concurrency=1)
        started = asyncio.Event()
        release = asyncio.Event()
        called = False

        async def running() -> None:
            started.set()
            await release.wait()

        async def queued() -> str:
            nonlocal called
            called = True
            return "bad"

        first = asyncio.create_task(scheduler.submit(running, priority=ProbePriority.DISCOVERY))
        await started.wait()
        second = asyncio.create_task(scheduler.submit(queued, priority=ProbePriority.MANUAL))
        await asyncio.sleep(0)
        second.cancel()
        try:
            await second
        except asyncio.CancelledError:
            pass
        release.set()
        await first
        await asyncio.sleep(0)
        assert not called
        await scheduler.close()

    asyncio.run(run())
