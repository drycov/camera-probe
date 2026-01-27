# camera_probe/domain/models/network_info.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class NetworkInfo:
    interface: Optional[str]

    ip: Optional[str]
    mask: Optional[str]
    cidr: Optional[int]

    gateway: Optional[str]
    mac: Optional[str]

    gateway_in_subnet: Optional[bool] = None
    subnet: Optional[bool] = None