# camera_probe/infrastructure/adapters/hikvision/adapter.py

from __future__ import annotations

import logging

from camera_probe.clients.hikvision.client import HikvisionIsapiClient
from camera_probe.domain.models.probe_result import ProbeResult
from camera_probe.infrastructure.adapters.base import BaseCameraAdapter
from camera_probe.infrastructure.adapters.decorators import register_adapter
from camera_probe.infrastructure.device.hikvision import HikvisionDeviceExtractor
from camera_probe.infrastructure.network.factory import NetworkExtractorFactory

logger = logging.getLogger(__name__)


@register_adapter("hikvision")
class HikvisionAdapter(BaseCameraAdapter):
    """
    Hikvision adapter via ISAPI client.
    """

    # camera_probe/infrastructure/adapters/hikvision/adapter.py

    async def probe(self) -> ProbeResult:
        client = HikvisionIsapiClient(
            ip=self.ip,
            username=self.username or "",
            password=self.password or "",
            timeout=self.timeout,
        )

        try:
            device_raw = await client.get_device_info_raw()
            network_raw = await client.get_network_info_raw()
        finally:
            client.close()

        extractor = NetworkExtractorFactory.create("hikvision")
        network = extractor.extract(network_raw) if network_raw else None

        device = HikvisionDeviceExtractor().extract(device_raw) if device_raw else {}

        return ProbeResult(
            ip=self.ip,
            vendor="Hikvision",
            confidence=0.95 if device else 0.6,
            model=device.get("model"),
            serial=device.get("serial"),
            mac=device.get("mac"),
            firmware=device.get("firmware"),
            network=network,
            raw={
                "device_raw": device_raw,
                "network_raw": network_raw,
            },
        )
