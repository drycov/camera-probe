# camera_probe/infrastructure/network/factory.py

from __future__ import annotations

from camera_probe.infrastructure.network.registry import NetworkExtractorRegistry
from camera_probe.infrastructure.network.generic import GenericNetworkExtractor
from camera_probe.infrastructure.vendor import normalize_vendor


class NetworkExtractorFactory:
    @staticmethod
    def create(vendor: str):
        normalized = normalize_vendor(vendor)
        if not normalized:
            raise RuntimeError("vendor is required for network extractor creation")

        extractor_cls = NetworkExtractorRegistry.get(normalized)

        if extractor_cls:
            return extractor_cls()

        # vendor известен, но extractor не зарегистрирован → ошибка
        if normalized != "generic":
            raise RuntimeError(
                f"Network extractor not registered for vendor: {normalized}"
            )

        return GenericNetworkExtractor()
