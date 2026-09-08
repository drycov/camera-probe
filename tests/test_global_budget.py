import asyncio
import threading

import pytest

from camera_probe.infrastructure.discovery.global_budget import DiscoveryBudget


@pytest.mark.asyncio
async def test_budget_is_shared_across_event_loops() -> None:
    budget = DiscoveryBudget(camera=1)
    entered = threading.Event()
    release = threading.Event()

    async def holder() -> None:
        async with budget.acquire("camera"):
            entered.set()
            await asyncio.to_thread(release.wait, 2)

    task = asyncio.create_task(holder())
    await asyncio.to_thread(entered.wait, 1)

    acquired = False

    def other_loop() -> None:
        nonlocal acquired
        async def run() -> None:
            nonlocal acquired
            async with budget.acquire("camera"):
                acquired = True
        asyncio.run(run())

    thread = threading.Thread(target=other_loop)
    thread.start()
    await asyncio.sleep(0.05)
    assert not acquired
    release.set()
    await task
    thread.join(timeout=2)
    assert acquired
