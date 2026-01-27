# camera_probe/infrastructure/network/decorators.py

from __future__ import annotations
from typing import Type
from camera_probe.infrastructure.network.registry import NetworkExtractorRegistry
from camera_probe.domain.ports.network_extractor import NetworkExtractor


def register_network_extractor(*vendors: str):
    def deco(cls: Type[NetworkExtractor]) -> Type[NetworkExtractor]:
        for v in vendors:
            NetworkExtractorRegistry.register(v, cls)
        return cls
    return deco
