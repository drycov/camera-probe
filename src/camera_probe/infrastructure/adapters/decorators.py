from __future__ import annotations

from typing import Type
from camera_probe.domain.ports.adapter import CameraAdapter
from camera_probe.infrastructure.adapters.registry import AdapterRegistry


def register_adapter(*vendors: str):
    def decorator(cls: Type[CameraAdapter]) -> Type[CameraAdapter]:
        for v in vendors:
            AdapterRegistry.register(v, cls)
        return cls
    return decorator
