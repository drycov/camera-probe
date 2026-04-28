from __future__ import annotations

# Ensure custom TRACE logging level exists even on direct submodule imports.
from camera_probe.infrastructure.logging.logging import setup_logging as _setup_logging

# ────────────────────────────────────────────────
# Public API functions
# ────────────────────────────────────────────────

from camera_probe.api import probe, scan

# ────────────────────────────────────────────────
# Domain models (stable contracts)
# ────────────────────────────────────────────────

from camera_probe.domain.models.probe_result import ProbeResult
from camera_probe.domain.models.network_info import NetworkInfo
from camera_probe.domain.models.ntp_info import NtpInfo

# ────────────────────────────────────────────────
# Version
# ────────────────────────────────────────────────

from camera_probe.version import __version__

# ────────────────────────────────────────────────
# Public exports
# ────────────────────────────────────────────────

__all__ = [
    "probe",
    "scan",
    "ProbeResult",
    "NetworkInfo",
    "NtpInfo",
    "__version__",
]
