from __future__ import annotations

import logging
from typing import Optional

from camera_probe.models.probe_result import ProbeResult
from camera_probe.services.probe_service import ProbeService

logger = logging.getLogger(__name__)


class CameraProbe:
    """
    Public entry point for camera_probe library.

    Stable API intended for:
    - CLI utilities
    - Backend services / ERP integrations
    - Tests
    - Scripts

    Contract:
    - async probe()
    - lazy initialization
    - optional async context manager
    """

    def __init__(self):
        self._service: ProbeService | None = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        # 🔑 force adapter registration
        import camera_probe.adapters  # noqa: F401

        self._service = ProbeService()
        self._initialized = True


    async def probe(
        self,
        *,
        ip: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: float = 5.0,
        force: bool = False,
    ) -> ProbeResult:
        """
        Probe a single camera.

        Args:
            ip: camera IP (required)
            username/password: optional credentials
            timeout: per-step timeout
            force: skip autodetect and go directly to force probing

        Returns:
            ProbeResult
        """
        if not ip:
            raise ValueError("IP address is required")

        self._ensure_initialized()
        assert self._service is not None  # for type-checkers

        logger.info(
            "camera_probe.probe | ip=%s | creds=%s | timeout=%.1fs | force=%s",
            ip,
            bool(username or password),
            timeout,
            force,
        )

        try:
            result = await self._service.probe(
                ip=ip,
                username=username,
                password=password,
                timeout=timeout,
                force=force,
            )

            # ─── Structured outcome logging (policy-based) ───
            if result.is_success(threshold=self._service.min_confidence):
                logger.info(
                    "probe success | ip=%s | vendor=%s | model=%s | conf=%.2f",
                    ip,
                    result.vendor,
                    result.model or "—",
                    result.confidence,
                )

            elif result.is_partial():
                logger.warning(
                    "probe partial | ip=%s | vendor=%s | conf=%.2f",
                    ip,
                    result.vendor or "—",
                    result.confidence,
                )

            else:
                logger.warning(
                    "probe failed | ip=%s | reason=%s",
                    ip,
                    result.error or "unknown",
                )

            return result

        except Exception:
            logger.exception("camera_probe critical failure | ip=%s", ip)
            raise

    # ────────────────────────────────────────────────
    # Async context manager support
    # ────────────────────────────────────────────────

    async def __aenter__(self) -> CameraProbe:
        await self._ensure_initialized()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        # Placeholder for future cleanup (connection pools, etc.)
        if exc_type:
            logger.debug("CameraProbe exited with exception")
        else:
            logger.debug("CameraProbe exited normally")

    def __repr__(self) -> str:
        state = "initialized" if self._initialized else "lazy"
        return f"CameraProbe({state})"

_global_probe: CameraProbe | None = None


def get_probe() -> CameraProbe:
    """
    Returns a global CameraProbe instance.

    Useful for long-lived applications to avoid repeated initialization.
    """
    global _global_probe
    if _global_probe is None:
        _global_probe = CameraProbe()
    return _global_probe
