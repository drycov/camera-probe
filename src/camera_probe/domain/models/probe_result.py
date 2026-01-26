# camera_probe/domain/models/probe_result.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .network_info import NetworkInfo
from .ntp_info import NtpInfo


@dataclass(slots=True)
class ProbeResult:
    """
    Canonical result of camera probing.

    Domain object:
    - no logic
    - no policy
    - only data
    """

    ip: str

    vendor: Optional[str]
    confidence: float

    model: Optional[str] = None
    serial: Optional[str] = None
    mac: Optional[str] = None
    firmware: Optional[str] = None

    network: Optional[NetworkInfo] = None
    ntp: Optional[NtpInfo] = None

    raw: Dict[str, Any] = field(default_factory=dict)
