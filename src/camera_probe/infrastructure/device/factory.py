# camera_probe/infrastructure/device/factory.py

from __future__ import annotations

from camera_probe.infrastructure.device.registry import DeviceExtractorRegistry
from camera_probe.infrastructure.adapters.vendor_aliases import VENDOR_ALIASES


class DeviceExtractorFactory:
    @staticmethod
    def create(vendor: str):
        key = VENDOR_ALIASES.get(vendor, vendor).lower()
        extractor_cls = DeviceExtractorRegistry.get(key)
        return extractor_cls() if extractor_cls else None
