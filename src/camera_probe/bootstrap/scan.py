from __future__ import annotations

from camera_probe.application.services.probe_service import ProbeService
from camera_probe.application.services.scan_service import ScanService
from camera_probe.bootstrap.probe import build_probe_service


def build_scan_service(*, probe_service: ProbeService | None = None) -> ScanService:
    """Build a scanner without creating a second discovery/registry graph."""
    return ScanService(probe_service or build_probe_service())
