from __future__ import annotations

import logging
from typing import Dict, Type

from camera_probe.domain.ports.network_extractor import NetworkExtractor

logger = logging.getLogger(__name__)


class NetworkExtractorRegistry:
    _items: Dict[str, Type[NetworkExtractor]] = {}
    _frozen: bool = False

    @classmethod
    def register(cls, vendor: str, extractor: Type[NetworkExtractor]) -> None:
        key = vendor.lower()

        if cls._frozen:
            raise RuntimeError(
                f"NetworkExtractorRegistry is frozen, cannot register: {key}"
            )

        if key in cls._items:
            raise RuntimeError(
                f"Network extractor already registered for vendor: {key}"
            )

        cls._items[key] = extractor

        logger.debug(
            "Network extractor registered | vendor=%s | class=%s",
            key,
            extractor.__name__,
        )

    @classmethod
    def get(cls, vendor: str) -> Type[NetworkExtractor] | None:
        return cls._items.get(vendor.lower())

    @classmethod
    def freeze(cls) -> None:
        cls._frozen = True
        logger.debug(
            "NetworkExtractorRegistry frozen | vendors=%s",
            sorted(cls._items.keys()),
        )

    @classmethod
    def all(cls) -> Dict[str, Type[NetworkExtractor]]:
        return dict(cls._items)
