from __future__ import annotations

import os

from camera_probe.application.services.probe_scheduler import ProbeScheduler
from camera_probe.application.services.probe_service import ProbeService
from camera_probe.infrastructure.adapters.factory import DefaultAdapterFactory
from camera_probe.infrastructure.discovery.engine import DiscoveryEngine
from camera_probe.infrastructure.network.auto_import import auto_import_network_extractors
from camera_probe.infrastructure.network.registry import NetworkExtractorRegistry


def build_probe_service(*, min_confidence: float = 0.5, enable_scheduler: bool | None = None) -> ProbeService:
    """Build the shared probe graph.

    Backward compatibility is preserved for direct ``ProbeService`` users.
    The application bootstrap enables the shared priority scheduler by default,
    while ``CAMERA_PROBE_ENABLE_PRIORITY_SCHEDULER=0`` restores direct mode.
    """
    discovery = DiscoveryEngine()
    adapters = DefaultAdapterFactory()
    auto_import_network_extractors("camera_probe.infrastructure.network")
    NetworkExtractorRegistry.freeze()

    if enable_scheduler is None:
        enable_scheduler = os.getenv("CAMERA_PROBE_ENABLE_PRIORITY_SCHEDULER", "1").lower() in {"1", "true", "yes", "on"}

    scheduler = ProbeScheduler() if enable_scheduler else None
    return ProbeService(
        discovery=discovery,
        adapters=adapters,
        min_confidence=min_confidence,
        scheduler=scheduler,
    )
