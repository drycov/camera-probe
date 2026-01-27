# camera_probe/application/services/scan_service.py
from __future__ import annotations

import asyncio
import logging
from ipaddress import ip_network
from typing import AsyncIterator, Callable, Optional, cast

from camera_probe.application.dto.scan_request import ScanRequest
from camera_probe.application.dto.probe_request import ProbeRequest
from camera_probe.application.services.probe_service import ProbeService
from camera_probe.domain.models.probe_result import ProbeResult

logger = logging.getLogger(__name__)


class ScanService:
    """
    Batch scan use case.

    Emits results via optional callback.
    """

    def __init__(self, probe_service: ProbeService) -> None:
        self._probe_service = probe_service

    async def scan(
        self,
        request: ScanRequest,
        *,
        on_result: Optional[Callable[[ProbeResult], None]] = None,
    ) -> AsyncIterator[ProbeResult]:
        if request.concurrency < 1:
            raise ValueError("concurrency must be >= 1")

        ip_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        result_queue: asyncio.Queue[object] = asyncio.Queue()
        sentinel = object()

        async def _enqueue_ips() -> None:
            for ip in ip_network(request.cidr, strict=False).hosts():
                await ip_queue.put(str(ip))
            for _ in range(request.concurrency):
                await ip_queue.put(None)

        async def _probe_ip() -> None:
            while True:
                ip = await ip_queue.get()
                if ip is None:
                    ip_queue.task_done()
                    break

                try:
                    probe_req = ProbeRequest(
                        ip=ip,
                        username=request.username,
                        password=request.password,
                        timeout=request.timeout,
                    )
                    result = await self._probe_service.probe(probe_req)
                except Exception as exc:
                    logger.exception("scan probe failed | ip=%s", ip)
                    result = ProbeResult(
                        ip=ip,
                        vendor=None,
                        confidence=0.0,
                        raw={"reason": "scan_probe_failed", "error": str(exc)},
                    )

                if on_result:
                    on_result(result)

                await result_queue.put(result)
                ip_queue.task_done()

            await result_queue.put(sentinel)

        producer_task = asyncio.create_task(_enqueue_ips())
        worker_tasks = [
            asyncio.create_task(_probe_ip()) for _ in range(request.concurrency)
        ]

        finished_workers = 0
        while finished_workers < len(worker_tasks):
            item = await result_queue.get()
            if item is sentinel:
                finished_workers += 1
                continue
            yield cast(ProbeResult, item)

        await producer_task
        await ip_queue.join()
        await asyncio.gather(*worker_tasks)
