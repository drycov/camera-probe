from __future__ import annotations

from abc import ABC
from typing import ClassVar, final, Any

from camera_probe.models.detect_result import DetectResult
from camera_probe.models.probe_result import ProbeResult
from camera_probe.probes.registry import ProbeRegistry


class CameraAdapter(ABC):
    """
    Base abstract adapter for camera vendors.

    Responsibilities:
    - detect_async(): lightweight / passive vendor detection (optional)
    - probe_async(): delegate full probing to registered Probe

    Contracts:
    - detect_async NEVER raises
    - probe_async ALWAYS returns ProbeResult
    - subclasses MUST define `vendor: ClassVar[str]`
    """

    vendor: ClassVar[str]

    # ──────────────────────────────────────────────
    # Init
    # ──────────────────────────────────────────────

    def __init__(
        self,
        ip: str,
        *,
        username: str = "",
        password: str = "",
        timeout: float = 5.0,
        **_: Any,
    ) -> None:
        if not ip:
            raise ValueError("ip is required")

        if timeout <= 0:
            raise ValueError("timeout must be positive")

        self.ip: str = ip
        self.username: str = username
        self.password: str = password
        self.timeout: float = timeout

    # ──────────────────────────────────────────────
    # Detection (optional, class-level)
    # ──────────────────────────────────────────────

    @classmethod
    async def detect_async(
        cls,
        ip: str,
        *,
        timeout: float = 5.0,
        **_: Any,
    ) -> DetectResult:
        """
        Default detection stub.

        Always returns DetectResult.
        Never raises.
        """
        try:
            return DetectResult(
                ip=ip,
                vendor=None,
                adapter_cls=cls,
                confidence=0.0,
                status="not_supported",
                evidence={
                    "adapter": cls.__name__,
                    "reason": "detect_async_not_implemented",
                },
            )
        except Exception as exc:
            # абсолютный safety-net, чтобы DiscoveryEngine не падал
            return DetectResult(
                ip=ip,
                vendor=None,
                adapter_cls=cls,
                confidence=0.0,
                status="error",
                evidence={
                    "adapter": cls.__name__,
                    "exception": type(exc).__name__,
                },
                error=str(exc),
            )

    # ──────────────────────────────────────────────
    # Probing (delegation to Probe)
    # ──────────────────────────────────────────────

    async def probe_async(self) -> ProbeResult:
        """
        Delegate probing to ProbeRegistry.

        Flow:
        1. Resolve Probe class by vendor
        2. Instantiate Probe
        3. Execute probe_async()
        """
        probe_cls = ProbeRegistry.get(self.vendor)

        if probe_cls is None:
            return ProbeResult(
                ip=self.ip,
                vendor=self.vendor,
                confidence=0.0,
                error=f"probe_not_registered:{self.vendor}",
                raw={
                    "adapter": self.__class__.__name__,
                },
            )

        try:
            probe = probe_cls(
                ip=self.ip,
                username=self.username,
                password=self.password,
                timeout=self.timeout,
            )
            return await probe.probe_async()

        except Exception as exc:
            return ProbeResult(
                ip=self.ip,
                vendor=self.vendor,
                confidence=0.0,
                error=f"probe_execution_failed:{type(exc).__name__}",
                raw={
                    "adapter": self.__class__.__name__,
                    "probe_cls": probe_cls.__name__,
                    "exception": str(exc),
                },
            )

    # ──────────────────────────────────────────────
    # Inheritance guard
    # ──────────────────────────────────────────────

    @final
    @classmethod
    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        if cls is CameraAdapter:
            return

        vendor = getattr(cls, "vendor", None)
        if not isinstance(vendor, str) or not vendor.strip():
            raise TypeError(
                f"{cls.__name__} must define non-empty "
                f"class attribute 'vendor: ClassVar[str]'"
            )
