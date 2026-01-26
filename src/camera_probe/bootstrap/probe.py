# camera_probe/bootstrap/probe.py
from __future__ import annotations

from camera_probe.application.services.probe_service import ProbeService
from camera_probe.infrastructure.adapters.factory import DefaultAdapterFactory
from camera_probe.infrastructure.discovery.engine import DiscoveryEngine



def build_probe_service(
    *,
    min_confidence: float = 0.7,
) -> ProbeService:
    """
    Build fully wired ProbeService.

    This is the ONLY place where:
    - application knows infrastructure
    - infrastructure meets domain
    """

    discovery = DiscoveryEngine()
    adapters = DefaultAdapterFactory()

    return ProbeService(
        discovery=discovery,
        adapters=adapters,
        min_confidence=min_confidence,
    )
