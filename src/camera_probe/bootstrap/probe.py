from __future__ import annotations

from camera_probe.application.services.probe_service import ProbeService
from camera_probe.infrastructure.adapters.factory import DefaultAdapterFactory
from camera_probe.infrastructure.discovery.engine import DiscoveryEngine

from camera_probe.infrastructure.network.auto_import import (
    auto_import_network_extractors,
)
from camera_probe.infrastructure.network.registry import NetworkExtractorRegistry

from camera_probe.infrastructure.adapters.auto_import import auto_import_adapters


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

    # 1️⃣ Discovery
    discovery = DiscoveryEngine()

    # 2️⃣ Adapters
    adapters = DefaultAdapterFactory()

    # 3️⃣ Auto-import infrastructure (SIDE EFFECTS)
    auto_import_network_extractors("camera_probe.infrastructure.network")
    auto_import_adapters("camera_probe.infrastructure.adapters")

    # 4️⃣ FREEZE registries (CRITICAL)
    NetworkExtractorRegistry.freeze()

    return ProbeService(
        discovery=discovery,
        adapters=adapters,
        min_confidence=min_confidence,
    )
