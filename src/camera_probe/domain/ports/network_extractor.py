# camera_probe/domain/services/network_extractor.py

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
from camera_probe.domain.models.network_info import NetworkInfo


class NetworkExtractor(ABC):
    @abstractmethod
    def extract(self, raw: Any) -> NetworkInfo | None:
        ...
