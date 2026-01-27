# camera_probe/infrastructure/network/generic.py

from __future__ import annotations
from typing import Optional, Dict, Any
import re


class GenericNetworkExtractor:
    """
    Best-effort extraction from key=value blobs
    """

    def extract(self, raw: str) -> Optional[Dict[str, Any]]:
        ip = re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", raw)
        if not ip:
            return None

        return {"ip": ip.group(0)}
