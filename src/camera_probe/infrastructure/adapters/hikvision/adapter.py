# camera_probe/infrastructure/adapters/hikvision/adapter.py

from __future__ import annotations

import logging

from camera_probe.domain.models.probe_result import ProbeResult
from camera_probe.infrastructure.adapters.base import BaseCameraAdapter
from camera_probe.infrastructure.adapters.decorators import register_adapter
from camera_probe.clients.hikvision.client import HikvisionIsapiClient

logger = logging.getLogger(__name__)


@register_adapter("hikvision")
class HikvisionAdapter(BaseCameraAdapter):
    """
    Hikvision adapter via ISAPI client.
    """

    async def probe(self) -> ProbeResult:
        client = HikvisionIsapiClient(
            ip=self.ip,
            username=self.username or "",
            password=self.password or "",
            timeout=self.timeout,
        )

        info = await client.get_device_info()

        if not info:
            raise RuntimeError("ISAPI deviceInfo unavailable")

        return ProbeResult(
            ip=self.ip,
            vendor="Hikvision",
            confidence=0.95,
            model=info.get("model"),
            serial=info.get("serial"),
            mac=info.get("mac"),
            firmware=info.get("firmware"),
            raw={"isapi": info},
        )
