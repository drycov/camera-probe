# camera_probe/application/services/probe_service.py

from __future__ import annotations

from typing import Optional
import logging

from camera_probe.application.dto.probe_request import ProbeRequest
from camera_probe.application.policies.confidence_policy import is_probe_success
from camera_probe.application.serializers.probe_result import serialize_dataclass
from camera_probe.application.services.probe_priority import ProbePriority
from camera_probe.application.services.probe_scheduler import ProbeScheduler
from camera_probe.domain.models.detect_result import DetectResult
from camera_probe.domain.models.probe_result import ProbeResult
from camera_probe.domain.ports.adapter_factory import AdapterFactory
from camera_probe.domain.ports.discovery import DiscoveryPort

logger = logging.getLogger(__name__)


class ProbeService:
    """Application-level probe use case with an opt-in priority scheduler.

    Existing ``probe(request)`` callers remain compatible: scheduling is only
    enabled when a scheduler is explicitly supplied. This keeps legacy API
    behaviour unchanged while allowing health/discovery/manual entry points to
    share a bounded priority queue.
    """

    def __init__(self, *, discovery: DiscoveryPort, adapters: AdapterFactory, min_confidence: float = 0.7, scheduler: ProbeScheduler | None = None) -> None:
        self._discovery = discovery
        self._adapters = adapters
        self._min_confidence = min_confidence
        self._scheduler = scheduler

    async def probe(self, request: ProbeRequest, *, priority: ProbePriority = ProbePriority.DISCOVERY) -> ProbeResult:
        self._validate_request(request)
        if self._scheduler is None:
            return await self._probe_direct(request)
        return await self._scheduler.submit(self._probe_direct(request), priority=priority)

    async def health_probe(self, request: ProbeRequest) -> ProbeResult:
        return await self.probe(request, priority=ProbePriority.HEALTH)

    async def discovery_probe(self, request: ProbeRequest) -> ProbeResult:
        return await self.probe(request, priority=ProbePriority.DISCOVERY)

    async def manual_probe(self, request: ProbeRequest) -> ProbeResult:
        return await self.probe(request, priority=ProbePriority.MANUAL)

    async def _probe_direct(self, request: ProbeRequest) -> ProbeResult:
        if self._should_force_first(request):
            return await self._force_probe(request)
        detect = await self._discover(request)
        result = await self._try_vendor_probe(detect, request)
        if result:
            return result
        if self._should_force_fallback(request):
            return await self._force_probe(request)
        return self._failure_result(request.ip, detect)

    async def _discover(self, request: ProbeRequest) -> DetectResult:
        return await self._discovery.detect(ip=request.ip, username=request.username, password=request.password)

    async def _try_vendor_probe(self, detect: DetectResult, request: ProbeRequest) -> Optional[ProbeResult]:
        if not self._can_vendor_probe(detect):
            return None
        try:
            adapter = self._adapters.create(vendor=detect.vendor, ip=request.ip, username=request.username, password=request.password, timeout=request.timeout)
            result = await adapter.probe()
        except Exception as exc:
            logger.warning("vendor probe failed | ip=%s vendor=%s error=%s", request.ip, detect.vendor, exc.__class__.__name__)
            logger.debug("vendor probe exception details", exc_info=True)
            return None
        if not result or not is_probe_success(result.confidence, self._min_confidence):
            return None
        return result

    async def _force_probe(self, request: ProbeRequest) -> ProbeResult:
        adapter = self._adapters.create(vendor="__force__", ip=request.ip, username=request.username, password=request.password, timeout=request.timeout)
        return await adapter.probe()

    def _should_force_first(self, request: ProbeRequest) -> bool:
        return bool(request.force and self._has_credentials(request))

    def _should_force_fallback(self, request: ProbeRequest) -> bool:
        return bool(request.prefer_force and self._has_credentials(request))

    def _can_vendor_probe(self, detect: DetectResult) -> bool:
        return bool(detect.vendor and is_probe_success(detect.confidence, self._min_confidence))

    @staticmethod
    def _has_credentials(request: ProbeRequest) -> bool:
        return bool(request.username or request.password)

    def _failure_result(self, ip: str, detect: DetectResult) -> ProbeResult:
        return ProbeResult(ip=ip, vendor=None, confidence=0.0, raw={"reason": "probe_failed", "detect": serialize_dataclass(detect)})

    @staticmethod
    def _validate_request(request: ProbeRequest) -> None:
        if not request.ip:
            raise ValueError("IP address is required")
