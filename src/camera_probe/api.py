from __future__ import annotations

from typing import AsyncIterator, Optional

from camera_probe.application.dto.probe_request import ProbeRequest
from camera_probe.application.dto.scan_request import ScanRequest
from camera_probe.bootstrap.probe import build_probe_service
from camera_probe.bootstrap.scan import build_scan_service
from camera_probe.domain.models.network_info import NetworkInfo
from camera_probe.domain.models.ntp_info import NtpInfo
from camera_probe.domain.models.probe_result import ProbeResult
from camera_probe.version import __version__


# Build one application graph. Creating it twice used to duplicate discovery
# engines and execute registry auto-import/freeze twice during module import.
_probe_service = build_probe_service()
_scan_service = build_scan_service(probe_service=_probe_service)


async def probe(
    *,
    ip: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
    timeout: float = 5.0,
    force: bool = False,
    prefer_force: bool = False,
) -> ProbeResult:
    request = ProbeRequest(
        ip=ip,
        username=username,
        password=password,
        timeout=timeout,
        force=force,
        prefer_force=prefer_force,
    )
    return await _probe_service.probe(request)


async def scan(
    *,
    cidr: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
    timeout: float = 5.0,
    concurrency: int = 20,
) -> AsyncIterator[ProbeResult]:
    """Scan a CIDR and yield ProbeResult objects."""
    request = ScanRequest(
        cidr=cidr,
        username=username,
        password=password,
        timeout=timeout,
        concurrency=concurrency,
    )
    async for result in _scan_service.scan(request):
        yield result


__all__ = [
    "probe",
    "scan",
    "ProbeResult",
    "ProbeRequest",
    "ScanRequest",
    "NetworkInfo",
    "NtpInfo",
    "__version__",
]
