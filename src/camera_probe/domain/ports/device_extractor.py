# camera_probe/domain/ports/device_extractor.py

from __future__ import annotations
from typing import Protocol, Optional, Dict


class DeviceExtractor(Protocol):
    def extract(self, raw: str) -> Optional[Dict[str, str]]:
        ...
