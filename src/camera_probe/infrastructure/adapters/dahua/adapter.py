# camera_probe/infrastructure/adapters/dahua/adapter.py

from __future__ import annotations

import logging

from camera_probe.clients.dahua.client import DahuaCgiClient
from camera_probe.domain.models.probe_result import ProbeResult
from camera_probe.infrastructure.adapters.base import BaseCameraAdapter
from camera_probe.infrastructure.adapters.decorators import register_adapter
from camera_probe.infrastructure.device.factory import DeviceExtractorFactory

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


        device_extractor = DeviceExtractorFactory.create("dahua")
        device = device_extractor.extract(raw_device) if device_extractor else None
        version = device_extractor.extract(raw_version) if device_extractor else None
        
        logger.error(device)
        logger.error(version)
        network = None
        if raw_network:
            from camera_probe.infrastructure.network.factory import NetworkExtractorFactory
            net_extractor = NetworkExtractorFactory.create("dahua")
            network = net_extractor.extract(raw_network)
            logger.error(network)


        return ProbeResult(
            ip=self.ip,
            vendor="Dahua",
            confidence=0.95 if device else 0.6,
            model=device.get("model") if device else None,
            serial=device.get("serial") if device else None,
            mac=(
                network.mac if network and network.mac
                else device.get("mac") if device
                else None
            ),
            firmware=device.get("firmware") if device else None,
            network=network,
            raw={
                "device": raw_device,
                "network": raw_network,
            },
        )


