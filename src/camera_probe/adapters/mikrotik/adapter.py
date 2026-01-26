from __future__ import annotations

import asyncio
import logging
from typing import Final, Any, Dict, Optional

import aiohttp

from camera_probe.adapters.base import CameraAdapter
from camera_probe.adapters.registry import AdapterRegistry
from camera_probe.clients.registry import ClientRegistry
from camera_probe.models.detect_result import DetectResult
from camera_probe.models.probe_result import ProbeResult, NetworkInfo, NtpInfo
from camera_probe.utils.mikrotik_fingerprint import fingerprint_mikrotik
logger = logging.getLogger(__name__)

@AdapterRegistry.register
class MikroTikAdapter(CameraAdapter):
    vendor = "mikrotik"

    @classmethod
    async def detect_async(cls, ip: str, timeout: float) -> DetectResult:
        fp = await fingerprint_mikrotik(ip)

        if not fp["evidence"]:
            return DetectResult.no_match(
                ip=ip,
                evidence={
                    "checked_ports": fp.get("checked_ports", []),
                },
            )

        return DetectResult.matched(
            ip=ip,
            vendor="mikrotik",
            adapter_cls=cls,
            confidence=fp["confidence"],
            evidence=fp["evidence"],
        )
