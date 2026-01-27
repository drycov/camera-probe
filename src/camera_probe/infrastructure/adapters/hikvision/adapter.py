# camera_probe/infrastructure/adapters/hikvision/adapter.py

from __future__ import annotations

import logging

from camera_probe.application.policies.extractor_policy import ExtractorPolicy
from camera_probe.clients.hikvision.client import HikvisionIsapiClient
from camera_probe.domain.models.probe_result import ProbeResult
from camera_probe.infrastructure.adapters.base import BaseCameraAdapter
from camera_probe.infrastructure.adapters.decorators import register_adapter
from camera_probe.infrastructure.device.factory import DeviceExtractorFactory
from camera_probe.infrastructure.device.generic import GenericDeviceExtractor
from camera_probe.infrastructure.device.hikvision import HikvisionDeviceExtractor
from camera_probe.infrastructure.device.registry import DeviceExtractorRegistry
from camera_probe.infrastructure.extractor.factory import ExtractorFactory
from camera_probe.infrastructure.network.factory import NetworkExtractorFactory
from camera_probe.infrastructure.network.generic import GenericNetworkExtractor
from camera_probe.infrastructure.network.registry import NetworkExtractorRegistry

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

        try:
            device_raw = await client.get_device_info_raw()
            network_raw = await client.get_network_info_raw()

        finally:
            client.close()

        # ──────────────────────────────────────────────
        # Device extractor (OPTIONAL)
        # ──────────────────────────────────────────────
        device_extractor = ExtractorFactory.create(
            vendor="hikvision",
            registry=DeviceExtractorRegistry,
            policy=ExtractorPolicy.OPTIONAL,
            fallback_cls=GenericDeviceExtractor,
        )

        device_info = (
            device_extractor.extract(device_raw)
            if device_extractor and device_raw
            else None
        )

        # ──────────────────────────────────────────────
        # Network extractor (STRICT)
        # ──────────────────────────────────────────────
        network = None
        if network_raw:
            network_extractor = ExtractorFactory.create(
                vendor="hikvision",
                registry=NetworkExtractorRegistry,
                policy=ExtractorPolicy.STRICT,
                fallback_cls=GenericNetworkExtractor,
            )
            network = network_extractor.extract(network_raw)

        # ──────────────────────────────────────────────
        # Assemble ProbeResult
        # ──────────────────────────────────────────────
        return ProbeResult(
            ip=self.ip,
            vendor="Hikvision",
            confidence=0.95 if device_info else 0.6,
            model=device_info.get("model") if device_info else None,
            serial=device_info.get("serial") if device_info else None,
            mac=device_info.get("mac") if device_info else None,
            firmware=device_info.get("firmware") if device_info else None,
            network=network,
            raw={
                "device_raw": device_raw,
                "network_raw": network_raw,
            },
        )
