from __future__ import annotations

from typing import Optional

from camera_probe.infrastructure.adapters.vendor_aliases import VENDOR_ALIASES


def normalize_vendor(vendor: Optional[str]) -> Optional[str]:
    if vendor is None:
        return None

    normalized = VENDOR_ALIASES.get(vendor, vendor).strip().lower()
    return normalized or None
