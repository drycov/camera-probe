
"""
Adapter bootstrap.

Importing this module guarantees that all camera adapters
are registered in Clients.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__: list[str] = []

def _safe_import(path: str) -> None:
    try:
        __import__(path, fromlist=["*"])
        logger.debug("probes bootstrap imported | module=%s", path)
    except Exception as exc:
        # не валим библиотеку из-за одного адаптера
        logger.warning("probes bootstrap failed | module=%s | error=%s", path, exc)

_safe_import("camera_probe.probes.hikvision")
_safe_import("camera_probe.probes.dahua")
_safe_import("camera_probe.probes.axis")
