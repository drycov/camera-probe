import logging
from typing import Optional

from camera_probe.discovery.engine import DiscoveryEngine
from camera_probe.discovery.config import DiscoveryConfig
from camera_probe.models.detect_result import DetectResult
from camera_probe.models.probe_result import ProbeResult
from camera_probe.orchestrators.force_probe import ForceProbeOrchestrator
from camera_probe.adapters.base import CameraAdapter

logger = logging.getLogger(__name__)


class ProbeService:
    """
    High-level probing service for IP cameras.

    Strategy:
    1. Optional forced probing (explicit or preferred)
    2. Vendor discovery
    3. Vendor-specific probing
    4. Forced probing as fallback (if credentials present)
    5. Minimal failure result
    """

    def __init__(
        self,
        *,
        config: Optional[DiscoveryConfig] = None,
        force_orchestrator: Optional[ForceProbeOrchestrator] = None,
        min_confidence: Optional[float] = None,
    ):
        self.config = config or DiscoveryConfig()
        self.min_confidence = min_confidence or self.config.min_confidence

        self.discovery = DiscoveryEngine(config=self.config)
        self.force = force_orchestrator or ForceProbeOrchestrator(
            min_confidence=self.min_confidence
        )

        logger.debug(
            "ProbeService initialized | min_confidence=%.2f | rtsp_passive=%s | http_timeout=%.1fs",
            self.min_confidence,
            self.config.enable_rtsp_passive,
            self.config.http_timeout,
        )

    # ────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────

    async def probe(
        self,
        *,
        ip: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: Optional[float] = None,
        force: bool = False,
        prefer_force: bool = False,
    ) -> ProbeResult:
        """
        Probe a single IP camera.

        Returns a ProbeResult in all cases (no None).
        """

        if not ip:
            raise ValueError("IP address is required")

        timeout = timeout or self.config.http_timeout
        has_creds = bool(username or password)

        logger.info(
            "probe start | ip=%s | force=%s | prefer_force=%s | creds=%s | timeout=%.1fs",
            ip, force, prefer_force, has_creds, timeout,
        )

        # 1. Explicit force always wins
        if force:
            return await self._force_probe(ip, username, password, timeout)

        # 2. Prefer force if credentials exist
        if prefer_force and has_creds:
            logger.debug("prefer_force enabled → skipping discovery ip=%s", ip)
            return await self._force_probe(ip, username, password, timeout)

        # 3. Discovery phase
        detect = await self._run_discovery(ip, username, password)

        # 4. Vendor adapter probe
        if self._can_use_vendor_adapter(detect):
            result = await self._run_vendor_probe(detect, ip, username, password, timeout)
            if self._is_good_result(result):
                return result

        # 5. Fallback to force probe
        if has_creds:
            logger.info("fallback to force probe ip=%s", ip)
            return await self._force_probe(ip, username, password, timeout)

        # 6. Hard failure
        logger.warning("probe failed ip=%s reason=no_vendor_no_creds", ip)
        return self._minimal_failure(ip, detect)

    # ────────────────────────────────────────────────
    # Internal steps
    # ────────────────────────────────────────────────

    async def _run_discovery(
        self,
        ip: str,
        username: Optional[str],
        password: Optional[str],
    ) -> DetectResult:
        detect = await self.discovery.detect_one(
            ip=ip,
            username=username,
            password=password,
        )

        if not detect:
            logger.warning("discovery returned None ip=%s", ip)
            return DetectResult(ip=ip, status="no_detection")

        logger.debug(
            "discovery result | ip=%s | vendor=%s | conf=%.2f | adapter=%s | status=%s",
            ip,
            detect.vendor,
            detect.confidence,
            detect.adapter_cls.__name__ if detect.adapter_cls else None,
            detect.status,
        )
        return detect

    async def _run_vendor_probe(
        self,
        detect: DetectResult,
        ip: str,
        username: Optional[str],
        password: Optional[str],
        timeout: float,
    ) -> Optional[ProbeResult]:
        try:
            adapter: CameraAdapter = detect.adapter_cls(
                ip=ip,
                username=username,
                password=password,
                timeout=timeout,
            )
            result = await adapter.probe_async()

            logger.info(
                "vendor probe completed | ip=%s | vendor=%s | conf=%.2f",
                ip, result.vendor, result.confidence,
            )
            return result

        except Exception:
            logger.exception(
                "vendor adapter probe failed ip=%s vendor=%s",
                ip, detect.vendor,
            )
            return None

    async def _force_probe(
        self,
        ip: str,
        username: Optional[str],
        password: Optional[str],
        timeout: float,
    ) -> ProbeResult:
        if not (username or password):
            logger.warning("force probe without credentials ip=%s", ip)

        try:
            result = await self.force.run(
                ip=ip,
                username=username or "",
                password=password or "",
                timeout=timeout,
            )

            logger.info(
                "force probe completed | ip=%s | vendor=%s | conf=%.2f",
                ip, result.vendor, result.confidence,
            )
            return result

        except Exception:
            logger.exception("force probe failed ip=%s", ip)
            return ProbeResult(
                ip=ip,
                vendor=None,
                confidence=0.0,
                raw={"reason": "force_probe_exception"},
            )

    # ────────────────────────────────────────────────
    # Decision helpers
    # ────────────────────────────────────────────────

    def _can_use_vendor_adapter(self, detect: DetectResult) -> bool:
        return (
            bool(detect.vendor)
            and bool(detect.adapter_cls)
            and detect.confidence >= self.min_confidence
        )

    def _is_good_result(self, result: Optional[ProbeResult]) -> bool:
        return bool(
            result
            and result.vendor
            and result.confidence >= self.min_confidence
        )

    def _minimal_failure(self, ip: str, detect: DetectResult) -> ProbeResult:
        return ProbeResult(
            ip=ip,
            vendor=None,
            confidence=0.0,
            raw={
                "reason": "no_sufficient_detection_and_no_credentials",
                "detect": detect.to_dict()
                if hasattr(detect, "to_dict")
                else vars(detect),
            },
        )
