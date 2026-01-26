# camera_probe/bootstrap/scan.py
from __future__ import annotations

from camera_probe.application.services.scan_service import ScanService
from camera_probe.bootstrap.probe import build_probe_service


def build_scan_service() -> ScanService:
    probe_service = build_probe_service()
    return ScanService(probe_service)
