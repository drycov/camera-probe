# camera_probe/application/dto/probe_request.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class ProbeRequest:
    """
    Input DTO for probe use case.
    """

    ip: str

    username: Optional[str] = None
    password: Optional[str] = None

    timeout: float = 5.0

    force: bool = False
    prefer_force: bool = False
