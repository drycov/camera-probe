from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List


# ────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────

def normalize_mac(mac: Optional[str]) -> Optional[str]:
    if not mac:
        return None

    clean = mac.replace("-", "").replace(":", "").lower()
    if len(clean) != 12 or not all(c in "0123456789abcdef" for c in clean):
        return None

    return ":".join(clean[i:i+2] for i in range(0, 12, 2))


def normalize_vendor(vendor: Optional[str]) -> Optional[str]:
    if not vendor:
        return None
    return vendor.strip().lower()


def clamp_confidence(value: Optional[float]) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(1.0, float(value)))


# ────────────────────────────────────────────────
# Model
# ────────────────────────────────────────────────

@dataclass(slots=True)
class CameraIdentity:
    """
    Normalized camera identity.

    This object is:
    - safe for persistence
    - safe for API serialization
    - stable across adapters
    """

    # ───────────── Core ─────────────
    ip: str
    vendor: Optional[str]
    confidence: float = 0.0

    # ───────────── Identity ─────────────
    serial: Optional[str] = None
    mac: Optional[str] = None
    model: Optional[str] = None
    firmware: Optional[str] = None

    # ───────────── Network ─────────────
    netmask: Optional[str] = None
    gateway: Optional[str] = None

    # ───────────── Provenance ─────────────
    adapter: Optional[str] = None
    source: Optional[str] = None

    # ───────────── Diagnostics ─────────────
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list, repr=False)

    # ───────────── Raw / Debug ─────────────
    raw: Optional[Dict[str, Any]] = field(default=None, repr=False)

    # ────────────────────────────────────
    # Lifecycle
    # ────────────────────────────────────

    def __post_init__(self) -> None:
        self.vendor = normalize_vendor(self.vendor)
        self.mac = normalize_mac(self.mac)
        self.confidence = clamp_confidence(self.confidence)

    # ────────────────────────────────────
    # State helpers
    # ────────────────────────────────────

    def is_identified(self) -> bool:
        """Vendor confidently identified."""
        return bool(self.vendor and self.confidence > 0.0)

    def is_complete(self) -> bool:
        """Full hardware identity available."""
        return bool(self.serial and self.mac and self.model)

    def has_network(self) -> bool:
        """Network configuration available."""
        return bool(self.netmask and self.gateway)

    def is_failed(self) -> bool:
        """Identity resolution failed."""
        return bool(self.error)

    # ────────────────────────────────────
    # Serialization
    # ────────────────────────────────────

    def to_dict(
        self,
        *,
        include_raw: bool = False,
        include_warnings: bool = True,
    ) -> Dict[str, Any]:
        """
        Serialize identity to dict.

        raw is excluded by default (debug-only).
        """
        data = asdict(self)

        if not include_raw:
            data.pop("raw", None)

        if not include_warnings:
            data.pop("warnings", None)

        return data
