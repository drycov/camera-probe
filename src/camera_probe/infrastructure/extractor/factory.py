from __future__ import annotations

import logging
from typing import Optional, Type, TypeVar

from camera_probe.application.policies.extractor_policy import ExtractorPolicy
from camera_probe.infrastructure.vendor import normalize_vendor

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ExtractorFactory:
    """
    Unified extractor factory with explicit creation policy.

    Supports:
    - STRICT   → raise if extractor missing
    - OPTIONAL → return None if extractor missing

    Registry contract:
    - get(vendor: str) -> Type[T] | None
    """

    @staticmethod
    def create(
        *,
        vendor: Optional[str],
        registry,
        policy: ExtractorPolicy,
        fallback_cls: Optional[Type[T]] = None,
    ) -> Optional[T]:
        # ──────────────────────────────────────────────
        # Vendor normalization
        # ──────────────────────────────────────────────
        normalized = normalize_vendor(vendor)
        if not normalized:
            if policy is ExtractorPolicy.STRICT:
                raise RuntimeError("vendor is required for STRICT extractor creation")
            return fallback_cls() if fallback_cls else None

        # ──────────────────────────────────────────────
        # Lookup
        # ──────────────────────────────────────────────
        extractor_cls = registry.get(normalized)
        if extractor_cls:
            return extractor_cls()

        # ──────────────────────────────────────────────
        # Missing extractor handling
        # ──────────────────────────────────────────────
        if policy is ExtractorPolicy.STRICT:
            raise RuntimeError(
                f"{registry.__class__.__name__}: extractor not registered for vendor={normalized}"
            )

        logger.debug(
            "extractor not found | vendor=%r normalized=%r policy=%s",
            vendor,
            normalized,
            policy.value,
        )

        return fallback_cls() if fallback_cls else None
