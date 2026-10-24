# camera_probe/domain/ports/discovery.py
from __future__ import annotations

from abc import ABC, abstractmethod

from camera_probe.domain.models.detect_result import DetectResult



class DiscoveryPort(ABC):
    """
    Vendor discovery interface.
    """

    @abstractmethod
    async def detect(
        self,
        *,
        ip: str,
        username: str | None = None,
        password: str | None = None,
        timeout_per_port: float = 1.5,
        max_total_timeout: float = 10.0,
    ) -> DetectResult:
        ...
