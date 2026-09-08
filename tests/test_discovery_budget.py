import asyncio

from camera_probe.infrastructure.discovery.budget import DiscoveryBudget


def test_budget_is_shared_across_async_tasks_and_respects_limit():
    budget = DiscoveryBudget(total=2, tcp=1, rtsp=1, http=1, onvif=1)
    active = 0
    peak = 0

    async def worker():
        nonlocal active, peak
        async with budget.slot("rtsp"):
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.02)
            active -= 1

    async def run():
        await asyncio.gather(*(worker() for _ in range(6)))

    asyncio.run(run())
    assert peak == 1


def test_budget_release_on_cancellation():
    budget = DiscoveryBudget(total=1, tcp=1, rtsp=1, http=1, onvif=1)

    async def run():
        entered = asyncio.Event()

        async def holder():
            async with budget.slot("rtsp"):
                entered.set()
                await asyncio.sleep(10)

        task = asyncio.create_task(holder())
        await entered.wait()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        async with budget.slot("rtsp"):
            return True

    assert asyncio.run(run()) is True
