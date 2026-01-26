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


class ProbeService:
    """
    Application-level use case for probing IP cameras.

    IMPORTANT:
    - no infrastructure imports
    - no logging
    - no vendor knowledge
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
        """
        Execute probe use case.

        Always returns ProbeResult (never None).
        """

        self._validate_request(request)

        has_creds = bool(request.username or request.password)

        # 1. Forced probe always wins
        if request.force and has_creds:
            return await self._force_probe(request)

        # 2. Discovery phase
        detect = await self._run_discovery(request)

        # 3. Vendor-specific probe
        if self._can_use_vendor_probe(detect):
            result = await self._run_vendor_probe(detect, request)
            if result and is_probe_success(result.confidence, self._min_confidence):
                return result

        # 4. Fallback to force probe
        if request.prefer_force and has_creds:
            return await self._force_probe(request)

        # 5. Hard failure
        return self._minimal_failure(request.ip, detect)

    # ────────────────────────────────────────────────
    # Internal steps
    # ────────────────────────────────────────────────

    async def _run_discovery(self, request: ProbeRequest) -> DetectResult:
        return await self._discovery.detect(
            ip=request.ip,
            username=request.username,
            password=request.password,
        )

    async def _run_vendor_probe(
        self,
        detect: DetectResult,
        request: ProbeRequest,
    ) -> Optional[ProbeResult]:
        adapter = self._adapters.create(
            vendor=detect.vendor,
            ip=request.ip,
            username=request.username,
            password=request.password,
            timeout=request.timeout,
        )
        return await adapter.probe()

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
    # Decision helpers
    # ────────────────────────────────────────────────

    def _can_use_vendor_probe(self, detect: DetectResult) -> bool:
        return bool(
            detect.vendor
            and is_probe_success(detect.confidence, self._min_confidence)
        )

    def _minimal_failure(self, ip: str, detect: DetectResult) -> ProbeResult:
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
