from __future__ import annotations

import asyncio
import logging
from ipaddress import ip_network
from typing import AsyncIterator, Awaitable, Callable, Optional, cast

from camera_probe.application.dto.probe_request import ProbeRequest
from camera_probe.application.dto.scan_request import ScanRequest
from camera_probe.application.services.probe_service import ProbeService
from camera_probe.domain.models.probe_result import ProbeResult

logger = logging.getLogger(__name__)

ResultCallback = Callable[[ProbeResult], None | Awaitable[None]]


class ScanService:
    """Bounded concurrent CIDR scanner.

    The scanner never materializes the whole CIDR into an asyncio.Queue. Workers
    pull the next address from a shared iterator under a lock, so a large /16 or
    /8 cannot consume unbounded memory. Cancellation also tears down every worker.
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
        worker_count = min(request.concurrency, max(1, request.concurrency))
        finished = object()

        async def next_ip() -> str | None:
            async with next_lock:
                try:
                    return str(next(hosts))
                except StopIteration:
                    return None

        async def worker() -> None:
            try:
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
                            # A consumer callback must never kill a scan worker.
                            logger.exception("scan result callback failed | ip=%s", ip)

                    await result_queue.put(result)
            except asyncio.CancelledError:
                raise

        workers = [asyncio.create_task(worker(), name=f"camera-probe-{i}") for i in range(worker_count)]
        remaining = len(workers)

        try:
            while remaining:
                done, _ = await asyncio.wait(workers, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    workers.remove(task)
                    remaining -= 1
                    # Surface unexpected worker failures instead of deadlocking on
                    # a missing sentinel/result.
                    task.result()

                while not result_queue.empty():
                    yield cast(ProbeResult, result_queue.get_nowait())

            while not result_queue.empty():
                yield result_queue.get_nowait()
        finally:
            for task in workers:
                if not task.done():
                    task.cancel()
            if workers:
                await asyncio.gather(*workers, return_exceptions=True)
