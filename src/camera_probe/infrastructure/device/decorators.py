# camera_probe/infrastructure/device/decorators.py

from __future__ import annotations
from typing import Type
from camera_probe.domain.ports.device_extractor import DeviceExtractor
from camera_probe.infrastructure.device.registry import DeviceExtractorRegistry


def register_device_extractor(vendor: str):
    def decorator(cls: Type[DeviceExtractor]) -> Type[DeviceExtractor]:
        DeviceExtractorRegistry.register(vendor, cls)
        return cls
    return decorator
