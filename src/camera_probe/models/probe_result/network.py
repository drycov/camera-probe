from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class NetworkInfo:
    ip: Optional[str] = None
    netmask: Optional[str] = None
    cidr: Optional[int] = None
    gateway: Optional[str] = None
    gateway_in_subnet: Optional[bool] = None
