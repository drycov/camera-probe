import asyncio
import logging
from typing import List, Type, Optional, Iterable

from camera_probe.adapters.base import CameraAdapter
from camera_probe.discovery.config import DiscoveryConfig
from camera_probe.discovery.rtsp_passive import rtsp_options
from camera_probe.models.detect_result import DetectResult
from camera_probe.adapters.registry import AdapterRegistry

logger = logging.getLogger(__name__)


class DiscoveryEngine:
    """
    Controlled async discovery engine.

    Stages (strict order):
    1. Passive HTTP detection (unauthenticated)
    2. RTSP passive evidence
    3. Authenticated HTTP detection (optional)
    """

    def __init__(
        self,
        *,
        adapters: Optional[Iterable[Type[CameraAdapter]]] = None,
        config: Optional[DiscoveryConfig] = None,
    ):
        self.adapters = list(adapters or AdapterRegistry.ordered())
        self.config = config or DiscoveryConfig()

        self._sem = asyncio.Semaphore(self.config.discovery_concurrency)

        logger.debug(
            "DiscoveryEngine initialized | adapters=%d | rtsp_passive=%s | min_conf=%.2f",
            len(self.adapters),
            self.config.enable_rtsp_passive,
            self.config.min_confidence,
        )

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    async def detect_one(
        self,
        ip: str,
        *,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> DetectResult:
        logger.info(
            "discovery start | ip=%s | auth=%s",
            ip,
            bool(username and password),
        )

        # 1. Passive HTTP
        result = await self._stage_passive_http(ip)
        if result.is_match():
            return result

        # 2. RTSP passive
        if self.config.enable_rtsp_passive:
            result = await self._stage_rtsp(ip)
            if result:
                return result

        # 3. Authenticated HTTP
        if username and password:
            result = await self._stage_authenticated_http(ip, username, password)
            if result.is_match():
                return result

        logger.info("discovery no_match | ip=%s", ip)
        return DetectResult.no_match(ip=ip)

    # ──────────────────────────────────────────────
    # Stage 1: passive HTTP
    # ──────────────────────────────────────────────

    async def _stage_passive_http(self, ip: str) -> DetectResult:
        best: Optional[DetectResult] = None

        async for result in self._run_adapters(ip, self._detect_passive):
            if not best or result.confidence > best.confidence:
                best = result

            if best.is_match() and best.confidence >= self.config.min_confidence:
                logger.info(
                    "discovery passive matched | ip=%s | vendor=%s | conf=%.2f",
                    ip,
                    best.vendor,
                    best.confidence,
                )
                return best

        return best or DetectResult.no_match(ip=ip)

    # ──────────────────────────────────────────────
    # Stage 2: RTSP passive
    # ──────────────────────────────────────────────

    async def _stage_rtsp(self, ip: str) -> Optional[DetectResult]:
        try:
            headers = await rtsp_options(
                ip,
                timeout=self.config.rtsp_timeout,
            )
        except Exception:
            logger.exception("rtsp passive failed ip=%s", ip)
            return None

        if not headers:
            return None

        server = (headers.get("Server") or "").upper()

        for adapter in self.adapters:
            if adapter.vendor and adapter.vendor.upper() in server:
                logger.info(
                    "discovery rtsp matched | ip=%s | vendor=%s",
                    ip,
                    adapter.vendor,
                )
                return DetectResult.matched(
                    ip=ip,
                    vendor=adapter.vendor,
                    adapter_cls=adapter,
                    confidence=self.config.rtsp_confidence,
                    evidence={"rtsp": headers},
                )

        return None

    # ──────────────────────────────────────────────
    # Stage 3: authenticated HTTP
    # ──────────────────────────────────────────────

    async def _stage_authenticated_http(
        self,
        ip: str,
        username: str,
        password: str,
    ) -> DetectResult:
        best: Optional[DetectResult] = None

        async for result in self._run_adapters(
            ip,
            self._detect_authenticated,
            username=username,
            password=password,
        ):
            if not best or result.confidence > best.confidence:
                best = result

            if best.is_match() and best.confidence >= self.config.min_confidence:
                logger.info(
                    "discovery auth matched | ip=%s | vendor=%s | conf=%.2f",
                    ip,
                    best.vendor,
                    best.confidence,
                )
                return best

        return best or DetectResult.no_match(ip=ip)

    # ──────────────────────────────────────────────
    # Adapter execution
    # ──────────────────────────────────────────────

    async def _run_adapters(self, ip: str, fn, **kwargs):
        async def run(adapter: Type[CameraAdapter]):
            async with self._sem:
                return await fn(adapter, ip, **kwargs)

        tasks = [asyncio.create_task(run(adapter)) for adapter in self.adapters]

        for task in asyncio.as_completed(tasks):
            yield await task

    # ──────────────────────────────────────────────
    # Adapter wrappers
    # ──────────────────────────────────────────────

    async def _detect_passive(
        self,
        adapter: Type[CameraAdapter],
        ip: str,
    ) -> DetectResult:
        if adapter.detect_async is CameraAdapter.detect_async:
            return DetectResult.no_match(
                ip=ip,
                evidence={"adapter": adapter.__name__, "reason": "detect_async_not_implemented"},
            )

        try:
            result = await adapter.detect_async(
                ip,
                timeout=self.config.http_timeout,
            )
            return self._attach_adapter(result, adapter)

        except Exception as exc:
            logger.debug(
                "detect_passive failed | ip=%s | adapter=%s | error=%s",
                ip,
                adapter.__name__,
                type(exc).__name__,
            )
            return DetectResult.error(
                ip=ip,
                error=type(exc).__name__,
                adapter_cls=adapter,
            )

    async def _detect_authenticated(
        self,
        adapter: Type[CameraAdapter],
        ip: str,
        username: str,
        password: str,
    ) -> DetectResult:
        detect_auth = getattr(adapter, "detect_auth_async", None)
        if not detect_auth:
            return DetectResult(
                ip=ip,
                vendor=None,
                adapter_cls=None,
                confidence=0.0,
                status="not_supported",
                evidence={"adapter": adapter.__name__},
            )

        try:
            result = await detect_auth(
                ip,
                username=username,
                password=password,
                timeout=self.config.http_timeout,
            )
            return self._attach_adapter(result, adapter)

        except Exception as exc:
            logger.debug(
                "detect_auth failed | ip=%s | adapter=%s | error=%s",
                ip,
                adapter.__name__,
                type(exc).__name__,
            )
            return DetectResult.error(
                ip=ip,
                error=type(exc).__name__,
                adapter_cls=adapter,
            )

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    def _attach_adapter(
        self,
        result: DetectResult,
        adapter: Type[CameraAdapter],
    ) -> DetectResult:
        if result.vendor:
            result.adapter_cls = adapter
            result.status = "matched"
        return result
