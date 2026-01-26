from __future__ import annotations

import logging
from typing import Any

from camera_probe.adapters.registry import AdapterRegistry

logger = logging.getLogger(__name__)


def debug(*, verbose: bool = False) -> dict[str, Any]:
    """
    Diagnostic snapshot of registered adapters.

    Intended for:
    - CLI --dump-detect
    - tests
    - support diagnostics

    Returns structured data, safe for JSON / print.
    """

    adapters = AdapterRegistry.ordered()

    snapshot = {
        "adapter_count": len(adapters),
        "vendors": [],
    }

    for adapter_cls in adapters:
        vendor = getattr(adapter_cls, "vendor", None)

        entry = {
            "vendor": vendor,
            "adapter": f"{adapter_cls.__module__}.{adapter_cls.__name__}",
            "has_detect": (
                adapter_cls.detect_async
                is not getattr(adapter_cls.__mro__[1], "detect_async", None)
            ),
        }

        snapshot["vendors"].append(entry)

        if verbose:
            logger.debug(
                "adapter registered | vendor=%s | cls=%s | detect=%s",
                vendor,
                entry["adapter"],
                entry["has_detect"],
            )

    return snapshot
