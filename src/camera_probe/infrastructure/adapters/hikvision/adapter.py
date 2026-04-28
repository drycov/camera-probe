# camera_probe/infrastructure/adapters/hikvision/adapter.py

from __future__ import annotations

import logging

from camera_probe.application.policies.extractor_policy import ExtractorPolicy
from camera_probe.clients.hikvision.client import HikvisionIsapiClient
from camera_probe.domain.models.probe_result import ProbeResult
from camera_probe.infrastructure.adapters.base import BaseCameraAdapter
from camera_probe.infrastructure.adapters.decorators import register_adapter
from camera_probe.infrastructure.device.generic import GenericDeviceExtractor
from camera_probe.infrastructure.device.registry import DeviceExtractorRegistry
from camera_probe.infrastructure.extractor.factory import ExtractorFactory
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
            network_source = client._last_network_info_path
        finally:
            client.close()

        device_info = self._extract_device_info(device_raw)
        network = self._extract_network_info(network_raw)
        confidence = self._resolve_confidence(
            device_info=device_info,
            network=network,
        )

        return ProbeResult(
            ip=self.ip,
            vendor="Hikvision",
            confidence=confidence,
            model=device_info.get("model") if device_info else None,
            serial=device_info.get("serial") if device_info else None,
            mac=device_info.get("mac") if device_info else None,
            firmware=device_info.get("firmware") if device_info else None,
            network=network,
            raw={
                "device_raw": device_raw,
                "network_raw": network_raw,
                "network_source": network_source,
                "device_info_available": bool(device_info),
                "network_info_available": bool(network),
            },
        )

    @staticmethod
    def _extract_device_info(device_raw: str | None):
        device_extractor = ExtractorFactory.create(
            vendor="hikvision",
            registry=DeviceExtractorRegistry,
            policy=ExtractorPolicy.OPTIONAL,
            fallback_cls=GenericDeviceExtractor,
        )
        if not device_extractor or not device_raw:
            return None
        return device_extractor.extract(device_raw)

    def _extract_network_info(self, network_raw: str | None):
        if not network_raw:
            return None

        network_extractor = self._create_network_extractor()
        if hasattr(network_extractor, "_target_ip"):
            network_extractor._target_ip = self.ip
        return network_extractor.extract(network_raw)

    @staticmethod
    def _create_network_extractor():
        network_extractor = ExtractorFactory.create(
            vendor="hikvision",
            registry=NetworkExtractorRegistry,
            policy=ExtractorPolicy.STRICT,
            fallback_cls=GenericNetworkExtractor,
        )
        return network_extractor

    @staticmethod
    def _resolve_confidence(*, device_info, network) -> float:
        if device_info:
            if (
                device_info.get("model")
                or device_info.get("serial")
                or device_info.get("mac")
            ):
                return 0.95
            return 0.8

        if network:
            return 0.72

        return 0.6
