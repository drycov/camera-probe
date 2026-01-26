# camera_probe/domain/ports/adapter.py
from __future__ import annotations

from abc import ABC, abstractmethod

from camera_probe.domain.models.probe_result import ProbeResult



class CameraAdapter(ABC):
    """
    Vendor-specific camera adapter.
    """

    @abstractmethod
    async def probe(self) -> ProbeResult:
        ...
