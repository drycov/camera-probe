import asyncio

from camera_probe.application.services.probe_priority import ProbePriority
from camera_probe.application.services.probe_scheduler import ProbeScheduler


def test_priority_is_honored_for_queued_work():
    async def run():
        scheduler = ProbeScheduler(concurrency=1)
        started = asyncio.Event()
        release = asyncio.Event()
        order = []

        async def running():
            started.set()
            await release.wait()
            order.append("running")

        async def job(name):
            order.append(name)
            return name

        first = asyncio.create_task(scheduler.submit(running(), priority=ProbePriority.DISCOVERY))
        await started.wait()
        low = asyncio.create_task(scheduler.submit(job("manual"), priority=ProbePriority.MANUAL))
        high = asyncio.create_task(scheduler.submit(job("health"), priority=ProbePriority.HEALTH))
        release.set()
        await first
        assert await high == "health"
        assert await low == "manual"
        assert order == ["running", "health", "manual"]
        await scheduler.close()

    asyncio.run(run())
