from __future__ import annotations

from camera_probe.domain.models.probe_result import ProbeResult
from camera_probe.infrastructure.adapters.base import BaseCameraAdapter
from camera_probe.infrastructure.adapters.decorators import register_adapter


@register_adapter("dahua")
class DahuaAdapter(BaseCameraAdapter):
    async def probe(self) -> ProbeResult:
        return ProbeResult(
            ip=self.ip,
            vendor="dahua",
            confidence=0.95,
            model="IPC-HDW2XXX",
            serial="DAHUA-STUB",
            mac=None,
            raw={"source": "dahua_stub"},
        )
