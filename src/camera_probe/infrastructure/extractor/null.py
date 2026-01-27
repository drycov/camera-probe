# camera_probe/infrastructure/extractor/null.py

from __future__ import annotations
from typing import Optional

from camera_probe.domain.models.network_info import NetworkInfo
from camera_probe.domain.models.ntp_info import NtpInfo
from camera_probe.domain.ports.device_extractor import DeviceExtractor


class NullDeviceExtractor(DeviceExtractor):
    """
    Null-object extractor.
    Used when vendor-specific extractor is unavailable.
    """

    def extract(self, raw: str) -> Optional[dict]:
        return None

    def extract_network(self, raw: str) -> Optional[NetworkInfo]:
        return None

    def extract_ntp(self, raw: str) -> Optional[NtpInfo]:
        return None
