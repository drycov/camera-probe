from __future__ import annotations

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
