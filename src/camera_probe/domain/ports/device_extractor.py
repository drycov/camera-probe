from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Optional

from camera_probe.domain.models.network_info import NetworkInfo
from camera_probe.domain.models.ntp_info import NtpInfo


class DeviceExtractor(ABC):
    """
    Extracts optional device-related information.

    IMPORTANT:
    - Must be safe (no exceptions on partial failure)
    - Used for enrichment, not for core detection
    """

    @abstractmethod
    def extract(self) -> Optional[Dict[str, str]]: ...

    @abstractmethod
    async def extract_network(self) -> NetworkInfo | None: ...

    @abstractmethod
    async def extract_ntp(self) -> NtpInfo | None: ...
