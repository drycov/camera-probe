import asyncio

import pytest

from camera_probe.application.dto.scan_request import ScanRequest
from camera_probe.application.services.scan_service import ScanService
from camera_probe.domain.models.probe_result import ProbeResult


class FakeProbeService:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0
        self.seen: list[str] = []

    async def probe(self, request):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.seen.append(request.ip)
        try:
            await asyncio.sleep(0)
            return ProbeResult(ip=request.ip, vendor=None, confidence=0.0)
        finally:
            self.active -= 1


def test_scan_is_bounded_and_returns_all_hosts():
    async def run():
        fake = FakeProbeService()
        service = ScanService(fake)
        results = [
            result
            async for result in service.scan(
                ScanRequest(cidr="192.0.2.0/29", concurrency=2, timeout=1.0)
            )
        ]
        assert len(results) == 6
        assert len({result.ip for result in results}) == 6
        assert fake.max_active <= 2

    asyncio.run(run())


def test_scan_callback_exception_does_not_kill_worker():
    async def run():
        fake = FakeProbeService()
        service = ScanService(fake)
        callback_calls = 0

        def callback(_):
            nonlocal callback_calls
            callback_calls += 1
            raise RuntimeError("consumer bug")

        results = [
            result
            async for result in service.scan(
                ScanRequest(cidr="192.0.2.0/30", concurrency=2, timeout=1.0),
                on_result=callback,
            )
        ]
        assert len(results) == 2
        assert callback_calls == 2

    asyncio.run(run())


def test_scan_rejects_non_positive_timeout():
    async def run():
        service = ScanService(FakeProbeService())
        with pytest.raises(ValueError, match="timeout must be > 0"):
            async for _ in service.scan(
                ScanRequest(cidr="192.0.2.0/30", concurrency=1, timeout=0)
            ):
                pass

    asyncio.run(run())
