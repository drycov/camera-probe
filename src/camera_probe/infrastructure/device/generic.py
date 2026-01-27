from __future__ import annotations

import logging

from camera_probe.domain.models.network_info import NetworkInfo
from camera_probe.domain.models.ntp_info import NtpInfo
from camera_probe.domain.ports.device_extractor import DeviceExtractor

logger = logging.getLogger(__name__)


class GenericDeviceExtractor(DeviceExtractor):
    """
    Generic fallback extractor.

    Strategy:
    - Never raises
    - Returns minimal / unknown information
    - Used when vendor-specific extractor is unavailable
    """

    async def extract_network(self) -> NetworkInfo | None:
        logger.debug("generic device extractor | network info unavailable")
        return None

    async def extract_ntp(self) -> NtpInfo | None:
        logger.debug("generic device extractor | ntp info unavailable")
        return None
