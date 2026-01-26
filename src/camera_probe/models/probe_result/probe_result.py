from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any
from .network import NetworkInfo
from .ntp import NtpInfo

# ──────────────────────────────────────────────
# Helpers (local, no cross-import coupling)
# ──────────────────────────────────────────────

def _normalize_vendor(vendor: Optional[str]) -> Optional[str]:
    return vendor.lower().strip() if vendor else None


def _normalize_mac(mac: Optional[str]) -> Optional[str]:
    if not mac:
        return None
    raw = mac.replace(":", "").replace("-", "").lower()
    if len(raw) != 12:
        return None
    return ":".join(raw[i:i+2] for i in range(0, 12, 2))


def _clamp_confidence(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


# ──────────────────────────────────────────────
# Probe Result
# ──────────────────────────────────────────────

@dataclass(slots=True)
class ProbeResult:
    """
    Final probe result.

    Represents FINAL outcome of probing, not discovery.
    Safe for:
    - persistence
    - API
    - audit / explanation
    """

    # ───────────── Core ─────────────
    ip: str
    vendor: Optional[str] = None
    confidence: float = 0.0

    # ───────────── Identity ─────────────
    model: Optional[str] = None
    serial: Optional[str] = None
    mac: Optional[str] = None
    firmware: Optional[str] = None

    # ───────────── Network / Services ─────────────
    network: Optional[NetworkInfo] = None
    ntp: Optional[NtpInfo] = None

    # ───────────── Diagnostics ─────────────
    error: Optional[str] = None
    warnings: list[str] = field(default_factory=list, repr=False)

    # ───────────── Raw / Debug ─────────────
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    # ──────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────

    def __post_init__(self) -> None:
        self.vendor = _normalize_vendor(self.vendor)
        self.mac = _normalize_mac(self.mac)
        self.confidence = _clamp_confidence(self.confidence)

    # ──────────────────────────────────────────────
    # State helpers (NO hardcoded policy)
    # ──────────────────────────────────────────────

    def is_success(self, *, threshold: float = 0.7) -> bool:
        return self.vendor is not None and self.confidence >= threshold


    def is_partial(self) -> bool:
        return self.vendor is not None and self.confidence > 0.0

    def is_failed(self) -> bool:
        return self.vendor is None or self.error is not None

    # ──────────────────────────────────────────────
    # Serialization
    # ──────────────────────────────────────────────

    def to_dict(
        self,
        *,
        include_raw: bool = False,
        include_warnings: bool = True,
    ) -> Dict[str, Any]:
        data = asdict(self)

        if not include_raw:
            data.pop("raw", None)

        if not include_warnings:
            data.pop("warnings", None)

        return data
