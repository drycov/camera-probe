# camera_probe/application/services/scan_service.py
from __future__ import annotations

import asyncio
from ipaddress import ip_network
from typing import Callable, List, Optional

from camera_probe.application.dto.scan_request import ScanRequest
from camera_probe.application.dto.probe_request import ProbeRequest
from camera_probe.application.services.probe_service import ProbeService
from camera_probe.domain.models.probe_result import ProbeResult


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
    ) -> List[ProbeResult]:
        semaphore = asyncio.Semaphore(request.concurrency)
        results: List[ProbeResult] = []

        async def _probe_ip(ip: str) -> None:
            async with semaphore:
                probe_req = ProbeRequest(
                    ip=ip,
                    username=request.username,
                    password=request.password,
                    timeout=request.timeout,
                )
                result = await self._probe_service.probe(probe_req)
                results.append(result)

                if on_result:
                    on_result(result)

        tasks = [
            asyncio.create_task(_probe_ip(str(ip)))
            for ip in ip_network(request.cidr, strict=False).hosts()
        ]

        await asyncio.gather(*tasks)
        return results
