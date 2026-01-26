from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Literal, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from camera_probe.adapters.base import CameraAdapter


# ────────────────────────────────────────────────
# Status contract
# ────────────────────────────────────────────────

DetectStatus = Literal[
    "matched",        # vendor confidently detected
    "no_match",       # detection attempted, no vendor
    "not_supported",  # adapter does not support this method
    "blacklisted",    # explicitly excluded
    "error",          # exception or invalid state
]


# ────────────────────────────────────────────────
# Model
# ────────────────────────────────────────────────

@dataclass(slots=True)
class DetectResult:
    """
    Result of discovery-stage vendor detection.

    This object is:
    - immutable in meaning (no side-effects in __post_init__)
    - decision-friendly
    - safe for logging and serialization
    """

    ip: str

    vendor: Optional[str] = None
    adapter_cls: Optional[Type["CameraAdapter"]] = None

    confidence: float = 0.0
    status: DetectStatus = "no_match"

    evidence: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    # ────────────────────────────────────────────────
    # Lifecycle
    # ────────────────────────────────────────────────

    def __post_init__(self) -> None:
        # clamp confidence only (no semantic mutation)
        self.confidence = max(0.0, min(1.0, float(self.confidence)))

    # ────────────────────────────────────────────────
    # State helpers
    # ────────────────────────────────────────────────

    def is_match(self) -> bool:
        """
        Strong vendor match.
        """
        return (
            self.status == "matched"
            and self.vendor is not None
            and self.adapter_cls is not None
            and self.confidence > 0.0
        )

    def is_error(self) -> bool:
        return self.status == "error"

    def is_empty(self) -> bool:
        return self.vendor is None and self.confidence == 0.0

    # ────────────────────────────────────────────────
    # Factories (optional but recommended)
    # ────────────────────────────────────────────────

    @classmethod
    def matched(
        cls,
        *,
        ip: str,
        vendor: str,
        adapter_cls: Type["CameraAdapter"],
        confidence: float,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> "DetectResult":
        return cls(
            ip=ip,
            vendor=vendor,
            adapter_cls=adapter_cls,
            confidence=confidence,
            status="matched",
            evidence=evidence or {},
        )

    @classmethod
    def no_match(
        cls,
        *,
        ip: str,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> "DetectResult":
        return cls(
            ip=ip,
            vendor=None,
            adapter_cls=None,
            confidence=0.0,
            status="no_match",
            evidence=evidence or {},
        )

    @classmethod
    def error(
        cls,
        *,
        ip: str,
        error: str,
        adapter_cls: Optional[Type["CameraAdapter"]] = None,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> "DetectResult":
        return cls(
            ip=ip,
            vendor=None,
            adapter_cls=adapter_cls,
            confidence=0.0,
            status="error",
            error=error,
            evidence=evidence or {},
        )
