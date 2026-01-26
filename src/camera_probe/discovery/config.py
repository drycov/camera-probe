from dataclasses import dataclass


@dataclass(slots=True)
class DiscoveryConfig:
    """
    Configuration for DiscoveryEngine.

    Scope:
    - vendor discovery ONLY
    - does NOT control full probe lifecycle
    """

    # ────────────────────────────────────────────────
    # HTTP discovery
    # ────────────────────────────────────────────────

    http_timeout: float = 2.0
    """
    Timeout for HTTP-based detection (passive + authenticated).
    """

    # ────────────────────────────────────────────────
    # RTSP passive discovery
    # ────────────────────────────────────────────────

    enable_rtsp_passive: bool = True
    rtsp_timeout: float = 1.5
    rtsp_confidence: float = 0.75
    """
    RTSP OPTIONS is used as passive evidence only.
    Confidence must be < 1.0 and < forced probe confidence.
    """

    # ────────────────────────────────────────────────
    # Concurrency control
    # ────────────────────────────────────────────────

    discovery_concurrency: int = 300
    """
    Maximum number of concurrent adapter detections.
    Protects event loop from fan-out explosion.
    """

    # ────────────────────────────────────────────────
    # Decision thresholds
    # ────────────────────────────────────────────────

    min_confidence: float = 0.60
    """
    Minimum confidence required to accept detection result.
    """

    # ────────────────────────────────────────────────
    # Validation (optional future hook)
    # ────────────────────────────────────────────────

    def __post_init__(self) -> None:
        if not 0.0 < self.min_confidence <= 1.0:
            raise ValueError("min_confidence must be in (0.0, 1.0]")

        if not 0.0 < self.rtsp_confidence <= 1.0:
            raise ValueError("rtsp_confidence must be in (0.0, 1.0]")

        if self.discovery_concurrency <= 0:
            raise ValueError("discovery_concurrency must be > 0")
