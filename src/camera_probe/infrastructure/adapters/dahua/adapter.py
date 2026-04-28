# camera_probe/infrastructure/adapters/dahua/adapter.py

from __future__ import annotations

import logging

from camera_probe.application.policies.extractor_policy import ExtractorPolicy
from camera_probe.clients.dahua.client import DahuaCgiClient
from camera_probe.domain.models.probe_result import ProbeResult
from camera_probe.infrastructure.adapters.base import BaseCameraAdapter
from camera_probe.infrastructure.adapters.decorators import register_adapter

from camera_probe.infrastructure.device.registry import DeviceExtractorRegistry
from camera_probe.infrastructure.extractor.factory import ExtractorFactory
from camera_probe.infrastructure.extractor.null import NullDeviceExtractor
from camera_probe.infrastructure.network.generic import GenericNetworkExtractor
from camera_probe.infrastructure.network.registry import NetworkExtractorRegistry

logger = logging.getLogger(__name__)


@register_adapter("dahua")
class DahuaAdapter(BaseCameraAdapter):

    async def probe(self) -> ProbeResult:
        client = DahuaCgiClient(
            ip=self.ip,
            username=self.username or "",
            password=self.password or "",
            timeout=self.timeout,
        )

        try:
            raw_device = await client.get_device_info()
            raw_network = await client.get_network_info()
            raw_version = await client.get_software_version()

        except Exception as exc:
            logger.exception(
                "dahua adapter probe failed | ip=%s | error=%s",
                self.ip,
                exc,
            )
            raise
        finally:
            client.close()

        # ──────────────────────────────────────────────
        # Device extractor (OPTIONAL)
        # ──────────────────────────────────────────────
        device_extractor = ExtractorFactory.create(
            vendor="dahua",
            registry=DeviceExtractorRegistry,
            policy=ExtractorPolicy.OPTIONAL,
            fallback_cls=NullDeviceExtractor
        )

        device_info = (
            device_extractor.extract(raw_device)
            if device_extractor and raw_device
            else None
        )

        version_info = (
            device_extractor.extract(raw_version)
            if device_extractor and raw_version
            else None
        )

        # ──────────────────────────────────────────────
        # Network extractor (STRICT)
        # ──────────────────────────────────────────────
        network = None
        if raw_network:
            network_extractor = ExtractorFactory.create(
                vendor="dahua",
                registry=NetworkExtractorRegistry,
                policy=ExtractorPolicy.STRICT,
                fallback_cls=GenericNetworkExtractor,
            )
            network = network_extractor.extract(raw_network)

        confidence = self._resolve_confidence(
            device_info=device_info,
            version_info=version_info,
            network=network,
        )

        # ──────────────────────────────────────────────
        # Assemble ProbeResult
        # ──────────────────────────────────────────────
        return ProbeResult(
            ip=self.ip,
            vendor="Dahua",
            confidence=confidence,
            model=device_info.get("model") if device_info else None,
            serial=device_info.get("serial") if device_info else None,
            mac=network.mac if network and network.mac else (
                device_info.get("mac") if device_info else None
            ),
            firmware=version_info.get("firmware") if version_info else None,
            network=network,
            raw={
                "device": raw_device,
                "network": raw_network,
                "version": raw_version,
                "device_info_available": bool(device_info),
                "version_info_available": bool(version_info),
                "network_info_available": bool(network),
            },
        )

    @staticmethod
    def _resolve_confidence(
        *,
        device_info,
        version_info,
        network,
    ) -> float:
        if device_info:
            if device_info.get("model") or device_info.get("serial") or device_info.get("mac"):
                return 0.95
            return 0.8

        if version_info and network:
            return 0.8

        if version_info or network:
            return 0.72

        return 0.6
