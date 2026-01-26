# camera_probe/domain/models/ntp_info.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class NtpInfo:
    enabled: Optional[bool]
    server: Optional[str]
    timezone: Optional[str]

    port: Optional[int] = None
    interval: Optional[int] = None
