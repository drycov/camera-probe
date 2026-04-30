from __future__ import annotations

import logging

from camera_probe.domain.models.probe_result import ProbeResult
from camera_probe.domain.ports.adapter import CameraAdapter
from camera_probe.infrastructure.adapters.registry import AdapterRegistry

logger = logging.getLogger(__name__)


class ForceProbeAdapter(CameraAdapter):
    def __init__(
        self,
        *,
        ip: str,
        username: str | None,
        password: str | None,
        timeout: float,
    ) -> None:
        self.ip = ip
        self.username = username
        self.password = password
        self.timeout = timeout

    async def probe(self) -> ProbeResult:
        attempted_vendors: list[str] = []
        best_result: ProbeResult | None = None

        for vendor, adapter_cls in AdapterRegistry.all().items():
            if vendor == "__force__":
                continue

            attempted_vendors.append(vendor)
            adapter = adapter_cls(
                ip=self.ip,
                username=self.username,
                password=self.password,
                timeout=self.timeout,
            )

            try:
                result = await adapter.probe()
            except Exception as exc:
                logger.debug(
                    "force probe adapter failed | ip=%s vendor=%s error=%s",
                    self.ip,
                    vendor,
                    exc.__class__.__name__,
                )
                continue

            if not result:
                continue

            if best_result is None or result.confidence > best_result.confidence:
                best_result = result

            if result.vendor and result.confidence >= 0.7:
                logger.debug(
                    "force probe adapter succeeded | ip=%s vendor=%s confidence=%.2f",
                    self.ip,
                    result.vendor,
                    result.confidence,
                )
                return result

        if best_result:
            logger.debug(
                "force probe returning best available result | ip=%s vendor=%s confidence=%.2f",
                self.ip,
                best_result.vendor,
                best_result.confidence,
            )
            return best_result

        return ProbeResult(
            ip=self.ip,
            vendor=None,
            confidence=0.0,
            raw={
                "reason": "force_probe_failed",
                "attempted_vendors": attempted_vendors,
            },
        )
