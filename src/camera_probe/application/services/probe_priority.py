from __future__ import annotations

from enum import IntEnum


class ProbePriority(IntEnum):
    """Scheduling priority for application-level probes."""

    HEALTH = 10
    DISCOVERY = 20
    MANUAL = 30
