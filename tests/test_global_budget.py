import asyncio
import threading

from camera_probe.infrastructure.discovery.budget import DiscoveryBudget


def test_budget_is_shared_across_event_loops() -> None:
    async def run() -> None:
        budget = DiscoveryBudget(total=1)
        entered = threading.Event()
        release = threading.Event()

        async def holder() -> None:
            async with budget.slot("total"):
                entered.set()
                await asyncio.to_thread(release.wait, 2)

        task = asyncio.create_task(holder())
        await asyncio.to_thread(entered.wait, 1)

        acquired = False

        def other_loop() -> None:
            nonlocal acquired

            async def nested() -> None:
                nonlocal acquired
                async with budget.slot("total"):
                    acquired = True

            asyncio.run(nested())

        thread = threading.Thread(target=other_loop)
        thread.start()
        await asyncio.sleep(0.05)
        assert not acquired
        release.set()
        await task
        thread.join(timeout=2)
        assert acquired

    asyncio.run(run())
