from __future__ import annotations

from typing import Type
from camera_probe.domain.ports.adapter import CameraAdapter
from camera_probe.infrastructure.adapters.registry import AdapterRegistry


def register_adapter(*vendors: str):
    if not vendors:
        raise ValueError("register_adapter requires at least one vendor")

    def decorator(cls: Type[CameraAdapter]) -> Type[CameraAdapter]:
        for v in vendors:
            key = v.strip().lower()
            if not key:
                continue
            AdapterRegistry.register(key, cls)
        return cls

    return decorator


