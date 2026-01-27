# camera_probe/infrastructure/network/factory.py

from __future__ import annotations
from camera_probe.infrastructure.network.registry import NetworkExtractorRegistry
from camera_probe.infrastructure.adapters.vendor_aliases import VENDOR_ALIASES
from camera_probe.infrastructure.network.generic import GenericNetworkExtractor


class NetworkExtractorFactory:
    @staticmethod
    def create(vendor: str):
        resolved = VENDOR_ALIASES.get(vendor, vendor)
        key = resolved.lower()

        extractor_cls = NetworkExtractorRegistry.get(key)

        if extractor_cls:
            return extractor_cls()

        # vendor известен, но extractor не зарегистрирован → ошибка
        if resolved.lower() != "generic":
            raise RuntimeError(
                f"Network extractor not registered for vendor: {resolved}"
            )

        return GenericNetworkExtractor()
