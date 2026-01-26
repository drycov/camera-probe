# camera_probe/application/dto/scan_request.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class ScanRequest:
    cidr: str

    username: Optional[str] = None
    password: Optional[str] = None

    timeout: float = 5.0
    concurrency: int = 20
