# camera_probe/infrastructure/device/factory.py

from __future__ import annotations

import logging
from typing import Optional, TypeVar

from camera_probe.domain.ports.device_extractor import DeviceExtractor
from camera_probe.infrastructure.device.registry import DeviceExtractorRegistry
from camera_probe.infrastructure.adapters.vendor_aliases import VENDOR_ALIASES

logger = logging.getLogger(__name__)




TExtractor = TypeVar("TExtractor", bound=DeviceExtractor)


class DeviceExtractorFactory:
    @staticmethod
    def create(vendor: Optional[str]) -> Optional[DeviceExtractor]:
        """
        Create extractor instance by vendor (with alias normalization).

        Returns:
            extractor instance or None (if vendor unsupported / unknown)
        """
        if not vendor:
            return None

        normalized = VENDOR_ALIASES.get(vendor, vendor).strip().lower()
        if not normalized:
            return None

        extractor_cls = DeviceExtractorRegistry.get(normalized)
        if not extractor_cls:
            logger.debug("device extractor not found | vendor=%r normalized=%r", vendor, normalized)
            return None

        return extractor_cls()
