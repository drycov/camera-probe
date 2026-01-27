# camera_probe/infrastructure/device/registry.py

from __future__ import annotations
from typing import Dict, Type
from camera_probe.domain.ports.device_extractor import DeviceExtractor


class DeviceExtractorRegistry:
    _items: Dict[str, Type[DeviceExtractor]] = {}

    @classmethod
    def register(cls, vendor: str, extractor: Type[DeviceExtractor]) -> None:
        cls._items[vendor.lower()] = extractor

    @classmethod
    def get(cls, vendor: str) -> Type[DeviceExtractor] | None:
        return cls._items.get(vendor.lower())
