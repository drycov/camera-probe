from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import ClassVar, Final

from camera_probe.models.probe_result import ProbeResult

logger = logging.getLogger(__name__)


class BaseProbe(ABC):
    """
    Abstract base class for all camera probes.

    Responsibilities:
    - communicate with a specific vendor camera
    - extract factual data only
    - return ProbeResult or raise exception

    MUST NOT:
    - perform vendor detection
    - perform fallback logic
    - make policy decisions
    """

    #: Unique vendor identifier (lowercase).
    #: Must be overridden in subclasses.
    vendor: ClassVar[str]

    def __init__(
        self,
        ip: str,
        username: str = "",
        password: str = "",
        timeout: float = 5.0,
    ) -> None:
        if not ip:
            raise ValueError("IP address is required")

        if timeout <= 0:
            raise ValueError("Timeout must be positive")

        # Immutable semantics (type-level contract)
        self.ip: Final[str] = ip
        self.username: Final[str] = username
        self.password: Final[str] = password
        self.timeout: Final[float] = timeout

        # Validate vendor at CLASS level
        vendor = getattr(type(self), "vendor", None)
        if not isinstance(vendor, str) or not vendor.strip():
            raise TypeError(
                f"{type(self).__name__} must define class attribute "
                f"`vendor: ClassVar[str]`"
            )

        logger.debug(
            "probe init | vendor=%s | ip=%s | auth=%s | timeout=%.1fs",
            vendor,
            ip,
            bool(username or password),
            timeout,
        )

    # ──────────────────────────────────────────────
    # Core contract
    # ──────────────────────────────────────────────

    @abstractmethod
    async def probe_async(self) -> ProbeResult:
        """
        Perform camera probing.

        Must return:
            ProbeResult — even if partial

        May raise:
            Exception — will be handled by orchestrators
        """
        raise NotImplementedError

    # ──────────────────────────────────────────────
    # Representation
    # ──────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"vendor={self.vendor!r}, "
            f"ip={self.ip!r}, "
            f"auth={bool(self.username or self.password)!r}, "
            f"timeout={self.timeout:.1f}s)"
        )
