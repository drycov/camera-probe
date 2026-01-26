from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class NtpInfo:
    enabled: Optional[bool] = None
    server: Optional[str] = None
    timezone: Optional[str] = None
    update_period: Optional[str] = None
    port: Optional[int] = None
    interval: Optional[int] = None
