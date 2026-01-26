# camera_probe/domain/models/detect_result.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class DetectResult:
    """
    Result of vendor detection phase.

    IMPORTANT:
    - no adapter classes
    - vendor is just a string
    """

    ip: str

    vendor: Optional[str]
    confidence: float

    method: Optional[str] = None
    evidence: Optional[dict] = None
    status: Optional[str] = None
