from __future__ import annotations

import asyncio
import logging
from ipaddress import ip_network
from typing import AsyncIterator, Awaitable, Callable, Optional

from camera_probe.application.dto.probe_request import ProbeRequest
from camera_probe.application.dto.scan_request import ScanRequest
from camera_probe.application.services.probe_service import ProbeService
from camera_probe.domain.models.probe_result import ProbeResult

logger = logging.getLogger(__name__)

ResultCallback = Callable[[ProbeResult], None | Awaitable[None]]


class ScanService:
    """Bounded concurrent CIDR scanner.

    The scanner streams addresses from the CIDR iterator instead of materializing
    them into a queue. Output is back-pressured, and cancellation always tears
    down workers.
    """

    def __init__(self, probe_service: ProbeService) -> None:
        self._probe_service = probe_service

    async def scan(
        self,
        request: ScanRequest,
        *,
        on_result: Optional[ResultCallback] = None,
    ) -> AsyncIterator[ProbeResult]:
        if request.concurrency < 1:
            raise ValueError("concurrency must be >= 1")
        if request.timeout <= 0:
            raise ValueError("timeout must be > 0")

        hosts = iter(ip_network(request.cidr, strict=False).hosts())
        next_lock = asyncio.Lock()
        result_queue: asyncio.Queue[ProbeResult] = asyncio.Queue(maxsize=request.concurrency * 2)

        async def next_ip() -> str | None:
            async with next_lock:
                try:
                    return str(next(hosts))
                except StopIteration:
                    return None

        async def worker() -> None:
            while True:
                ip = await next_ip()
                if ip is None:
                    return

                try:
                    result = await self._probe_service.probe(
                        ProbeRequest(
                            ip=ip,
                            username=request.username,
                            password=request.password,
                            timeout=request.timeout,
                        )
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.exception("scan probe failed | ip=%s", ip)
                    result = ProbeResult(
                        ip=ip,
                        vendor=None,
                        confidence=0.0,
                        raw={"reason": "scan_probe_failed", "error": str(exc)},
                    )

                if on_result:
                    try:
                        callback_result = on_result(result)
                        if callback_result is not None:
                            await callback_result
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        # Consumer callbacks are isolated from scan workers.
                        logger.exception("scan result callback failed | ip=%s", ip)

                await result_queue.put(result)

        workers = [
            asyncio.create_task(worker(), name=f"camera-probe-{i}")
            for i in range(request.concurrency)
        ]
        get_result = asyncio.create_task(result_queue.get())

        try:
            while workers or not result_queue.empty():
                wait_set = [task for task in workers if not task.done()]
                if get_result not in wait_set:
                    wait_set.append(get_result)

                done, _ = await asyncio.wait(wait_set, return_when=asyncio.FIRST_COMPLETED)

                if get_result in done:
                    yield get_result.result()
                    get_result = asyncio.create_task(result_queue.get())

                for task in list(workers):
                    if task in done:
                        workers.remove(task)
                        task.result()  # surface unexpected worker failure

                if not workers and not result_queue.empty():
                    while not result_queue.empty():
                        yield result_queue.get_nowait()
                    get_result.cancel()
                    await asyncio.gather(get_result, return_exceptions=True)
                    break
        finally:
            if not get_result.done():
                get_result.cancel()
            await asyncio.gather(get_result, return_exceptions=True)
            for task in workers:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
