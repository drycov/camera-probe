# camera_probe/application/services/probe_service.py

from __future__ import annotations

from typing import Optional

from camera_probe.application.dto.probe_request import ProbeRequest
from camera_probe.application.policies.confidence_policy import is_probe_success
from camera_probe.application.serializers.probe_result import serialize_dataclass
from camera_probe.domain.models.detect_result import DetectResult
from camera_probe.domain.models.probe_result import ProbeResult
from camera_probe.domain.ports.adapter_factory import AdapterFactory
from camera_probe.domain.ports.discovery import DiscoveryPort
import logging

logger = logging.getLogger(__name__)


class ProbeService:
    """
    Application-level use case for probing IP cameras.

    Responsibilities:
    - orchestrate probe flow
    - select strategy
    - return deterministic ProbeResult
    """

    def __init__(
        self,
        *,
        discovery: DiscoveryPort,
        adapters: AdapterFactory,
        min_confidence: float = 0.7,
    ) -> None:
        self._discovery = discovery
        self._adapters = adapters
        self._min_confidence = min_confidence

    # ────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────

    async def probe(self, request: ProbeRequest) -> ProbeResult:
        self._validate_request(request)

        # 1. Forced strategy (explicit)
        if self._should_force_first(request):
            return await self._force_probe(request)

        # 2. Discovery
        detect = await self._discover(request)

        # 3. Vendor strategy
        result = await self._try_vendor_probe(detect, request)
        if result:
            return result

        # 4. Forced strategy (fallback)
        if self._should_force_fallback(request):
            return await self._force_probe(request)

        # 5. Hard failure
        return self._failure_result(request.ip, detect)

    # ────────────────────────────────────────────────
    # Phases
    # ────────────────────────────────────────────────

    async def _discover(self, request: ProbeRequest) -> DetectResult:
        return await self._discovery.detect(
            ip=request.ip,
            username=request.username,
            password=request.password,
        )

    async def _try_vendor_probe(
        self,
        detect: DetectResult,
        request: ProbeRequest,
    ) -> Optional[ProbeResult]:
        if not self._can_vendor_probe(detect):
            return None

        try:
            adapter = self._adapters.create(
                vendor=detect.vendor,
                ip=request.ip,
                username=request.username,
                password=request.password,
                timeout=request.timeout,
            )
            result = await adapter.probe()
        except Exception as exc:
            logger.warning(
                "vendor probe failed with exception | ip=%s vendor=%s error=%s",
                request.ip,
                detect.vendor,
                exc.__class__.__name__,
            )
            logger.debug("vendor probe exception details", exc_info=True)
            return None

        if not result:
            logger.info(
                "vendor probe returned no result | ip=%s vendor=%s",
                request.ip,
                detect.vendor,
            )
            return None

        if not is_probe_success(result.confidence, self._min_confidence):
            logger.info(
                "vendor probe confidence too low | ip=%s vendor=%s confidence=%.2f min=%.2f",
                request.ip,
                detect.vendor,
                result.confidence,
                self._min_confidence,
            )
            return None

        return result

    async def _force_probe(self, request: ProbeRequest) -> ProbeResult:
        adapter = self._adapters.create(
            vendor="__force__",
            ip=request.ip,
            username=request.username,
            password=request.password,
            timeout=request.timeout,
        )
        return await adapter.probe()

    # ────────────────────────────────────────────────
    # Decisions
    # ────────────────────────────────────────────────

    def _should_force_first(self, request: ProbeRequest) -> bool:
        return bool(request.force and self._has_credentials(request))

    def _should_force_fallback(self, request: ProbeRequest) -> bool:
        return bool(request.prefer_force and self._has_credentials(request))

    def _can_vendor_probe(self, detect: DetectResult) -> bool:
        return bool(
            detect.vendor and is_probe_success(detect.confidence, self._min_confidence)
        )

    @staticmethod
    def _has_credentials(request: ProbeRequest) -> bool:
        return bool(request.username or request.password)

    # ────────────────────────────────────────────────
    # Results
    # ────────────────────────────────────────────────

    def _failure_result(self, ip: str, detect: DetectResult) -> ProbeResult:
        return ProbeResult(
            ip=ip,
            vendor=None,
            confidence=0.0,
            raw={
                "reason": "probe_failed",
                "detect": serialize_dataclass(detect),
            },
        )

    # ────────────────────────────────────────────────
    # Validation
    # ────────────────────────────────────────────────

    @staticmethod
    def _validate_request(request: ProbeRequest) -> None:
        if not request.ip:
            raise ValueError("IP address is required")
