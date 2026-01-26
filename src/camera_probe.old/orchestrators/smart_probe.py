from __future__ import annotations

import asyncio
import logging
from typing import Optional

from camera_probe.discovery.engine import DiscoveryEngine
from camera_probe.discovery.config import DiscoveryConfig
from camera_probe.models.detect_result import DetectResult
from camera_probe.models.probe_result import ProbeResult
from camera_probe.orchestrators.force_probe import ForceProbeOrchestrator
from camera_probe.adapters.base import CameraAdapter

logger = logging.getLogger(__name__)


class SmartProbeOrchestrator:
    """
    Smart orchestrator for camera probing.

    Default order:
    1) DiscoveryEngine (vendor + adapter)
    2) Vendor adapter probe (if confident)
    3) ForceProbe fallback (if creds exist OR force_fallback=True)
    4) Minimal failure result
    """

    def __init__(
        self,
        *,
        config: Optional[DiscoveryConfig] = None,
        discovery: Optional[DiscoveryEngine] = None,
        force_orchestrator: Optional[ForceProbeOrchestrator] = None,
    ):
        self.config = config or DiscoveryConfig()

        # allow DI for tests
        self.discovery = discovery or DiscoveryEngine(config=self.config)
        self.force = force_orchestrator or ForceProbeOrchestrator(
            min_confidence=self.config.min_confidence
        )

        self.min_confidence = self.config.min_confidence

        logger.debug(
            "SmartProbeOrchestrator initialized | rtsp_passive=%s | min_conf=%.2f | http_timeout=%.1fs",
            self.config.enable_rtsp_passive,
            self.min_confidence,
            self.config.http_timeout,
        )

    async def run(
        self,
        ip: str,
        *,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: Optional[float] = None,
        force_fallback: bool = False,
        total_timeout: Optional[float] = None,
    ) -> ProbeResult:
        """
        Probe a single camera.

        Args:
            ip: camera IP
            username/password: optional credentials
            timeout: per-step timeout (adapter/force/discovery HTTP timeout override)
            force_fallback: skip discovery and go directly to force probe
            total_timeout: optional hard timeout for the whole orchestration
        """

        if not ip:
            raise ValueError("ip is required")

        step_timeout = timeout or self.config.http_timeout
        has_creds = bool(username or password)

        logger.info(
            "smart_probe start | ip=%s | force=%s | creds=%s | step_timeout=%.1fs | total_timeout=%s",
            ip, force_fallback, has_creds, step_timeout,
            f"{total_timeout:.1f}s" if total_timeout else "—",
        )

        async def _execute() -> ProbeResult:
            detect: Optional[DetectResult] = None

            # 1) Discovery → vendor adapter (unless forced skip)
            if not force_fallback:
                detect = await self.discovery.detect_one(
                    ip=ip,
                    username=username,
                    password=password,
                )

                logger.debug(
                    "discovery result | ip=%s | vendor=%s | conf=%.2f | adapter=%s | status=%s",
                    ip,
                    detect.vendor or "—",
                    detect.confidence,
                    detect.adapter_cls.__name__ if detect.adapter_cls else "—",
                    detect.status,
                )

                if detect.is_match() and detect.confidence >= self.min_confidence:
                    result = await self._run_vendor_adapter(
                        detect=detect,
                        ip=ip,
                        username=username,
                        password=password,
                        timeout=step_timeout,
                    )
                    if self._is_good_result(result):
                        return result

            # 2) Force probe fallback
            if has_creds or force_fallback:
                return await self._run_force_probe(
                    ip=ip,
                    username=username,
                    password=password,
                    timeout=step_timeout,
                    force_requested=force_fallback,
                    detect=detect,
                )

            # 3) No creds + no confident vendor
            logger.warning("smart_probe failed | ip=%s | reason=no_vendor_no_creds", ip)
            return self._failure_no_creds(ip, detect)

        if total_timeout:
            try:
                return await asyncio.wait_for(_execute(), timeout=total_timeout)
            except asyncio.TimeoutError:
                logger.warning(
                    "smart_probe total_timeout | ip=%s | total_timeout=%.1fs",
                    ip, total_timeout,
                )
                return ProbeResult(
                    ip=ip,
                    vendor=None,
                    confidence=0.0,
                    error="total_timeout",
                    raw={"reason": "orchestrator_timeout"},
                )

        return await _execute()

    # ────────────────────────────────────────────────
    # Execution helpers
    # ────────────────────────────────────────────────

    async def _run_vendor_adapter(
        self,
        *,
        detect: DetectResult,
        ip: str,
        username: Optional[str],
        password: Optional[str],
        timeout: float,
    ) -> Optional[ProbeResult]:
        try:
            adapter: CameraAdapter = detect.adapter_cls(  # type: ignore[misc]
                ip=ip,
                username=username,
                password=password,
                timeout=timeout,
            )

            result = await adapter.probe_async()

            logger.info(
                "vendor probe completed | ip=%s | vendor=%s | conf=%.2f",
                ip, result.vendor or "—", result.confidence,
            )
            if not self._is_good_result(result):
                logger.warning(
                    "vendor probe weak | ip=%s | vendor=%s | conf=%.2f",
                    ip, result.vendor or "—", result.confidence,
                )
            return result

        except Exception:
            logger.exception(
                "vendor probe failed | ip=%s | vendor=%s",
                ip, detect.vendor or "—",
            )
            return None

    async def _run_force_probe(
        self,
        *,
        ip: str,
        username: Optional[str],
        password: Optional[str],
        timeout: float,
        force_requested: bool,
        detect: Optional[DetectResult],
    ) -> ProbeResult:
        logger.info(
            "force fallback | ip=%s | force_requested=%s | creds=%s",
            ip, force_requested, bool(username or password),
        )

        try:
            result = await self.force.run(
                ip=ip,
                username=username or "",
                password=password or "",
                timeout=timeout,
            )

            logger.info(
                "force probe completed | ip=%s | vendor=%s | conf=%.2f",
                ip, result.vendor or "—", result.confidence,
            )
            if not self._is_good_result(result):
                logger.warning(
                    "force probe weak | ip=%s | vendor=%s | conf=%.2f",
                    ip, result.vendor or "—", result.confidence,
                )

            # attach discovery context (debug-only)
            if detect:
                result.raw.setdefault("detect", _safe_detect_dict(detect))

            return result

        except Exception:
            logger.exception("force probe failed | ip=%s", ip)
            return ProbeResult(
                ip=ip,
                vendor=None,
                confidence=0.0,
                error="force_probe_exception",
                raw={
                    "reason": "force_probe_failed",
                    "detect": _safe_detect_dict(detect) if detect else None,
                },
            )

    # ────────────────────────────────────────────────
    # Result policy
    # ────────────────────────────────────────────────

    def _is_good_result(self, result: Optional[ProbeResult]) -> bool:
        return bool(result and result.vendor and result.confidence >= self.min_confidence and result.error is None)

    def _failure_no_creds(self, ip: str, detect: Optional[DetectResult]) -> ProbeResult:
        return ProbeResult(
            ip=ip,
            vendor=None,
            confidence=0.0,
            error="no_sufficient_detection_and_no_credentials",
            raw={
                "reason": "no_vendor_and_no_creds",
                "detect": _safe_detect_dict(detect) if detect else None,
            },
        )


# ────────────────────────────────────────────────
# Public high-level API
# ────────────────────────────────────────────────

async def probe(
    ip: str,
    *,
    username: str | None = None,
    password: str | None = None,
    timeout: float = 5.0,
    force: bool = False,
    total_timeout: float | None = None,
) -> ProbeResult:
    """
    Thin wrapper around SmartProbeOrchestrator.

    timeout: per-step timeout passed into adapters / force
    total_timeout: hard timeout for whole orchestration (optional)
    """
    orchestrator = SmartProbeOrchestrator()
    return await orchestrator.run(
        ip,
        username=username,
        password=password,
        timeout=timeout,
        force_fallback=force,
        total_timeout=total_timeout,
    )


def _safe_detect_dict(detect: Optional[DetectResult]) -> Optional[dict]:
    if not detect:
        return None
    # adapter_cls is not JSON-serializable; keep name only
    return {
        "ip": detect.ip,
        "vendor": detect.vendor,
        "confidence": detect.confidence,
        "status": detect.status,
        "error": detect.error,
        "evidence": detect.evidence,
        "adapter": detect.adapter_cls.__name__ if detect.adapter_cls else None,
    }
