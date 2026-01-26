"""
Adapter bootstrap.

Importing this module guarantees that all camera adapters
are registered in AdapterRegistry.

Design goals:
- Safe imports (no hard crash on broken adapter)
- Deterministic registration order
- Zero side-effects outside registration
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__: list[str] = []


def _safe_import(module_path: str) -> None:
    """
    Safely import adapter module.

    Any exception is logged but does NOT break library initialization.
    This is critical for:
    - optional adapters
    - partial installations
    - forward compatibility
    """
    try:
        __import__(module_path, fromlist=["*"])
        logger.debug(
            "adapter bootstrap imported | module=%s",
            module_path,
        )
    except Exception as exc:
        logger.warning(
            "adapter bootstrap failed | module=%s | error=%s",
            module_path,
            exc,
        )


# ──────────────────────────────────────────────
# Built-in adapters
# ──────────────────────────────────────────────

_safe_import("camera_probe.adapters.hikvision")
_safe_import("camera_probe.adapters.dahua")
_safe_import("camera_probe.adapters.axis")
_safe_import("camera_probe.adapters.mikrotik")

# ──────────────────────────────────────────────
# Debug / diagnostics (no adapters, only helpers)
# ──────────────────────────────────────────────

_safe_import("camera_probe.adapters.debug")
