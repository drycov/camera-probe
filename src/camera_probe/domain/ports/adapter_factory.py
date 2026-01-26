# camera_probe/domain/ports/adapter_factory.py
from __future__ import annotations

from abc import ABC, abstractmethod

from camera_probe.domain.ports.adapter import CameraAdapter



class AdapterFactory(ABC):
    """
    Factory for vendor adapters.
    """

    @abstractmethod
    def create(
        self,
        *,
        vendor: str,
        ip: str,
        username: str | None,
        password: str | None,
        timeout: float,
    ) -> CameraAdapter:
        ...
