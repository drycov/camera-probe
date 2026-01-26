# camera_probe/infrastructure/fingerprints/registry.py
from __future__ import annotations

import logging
from typing import Any, Optional

from camera_probe.infrastructure.fingerprints.base import Fingerprint

from camera_probe.infrastructure.fingerprints.dahua import DahuaFingerprint
from camera_probe.infrastructure.fingerprints.hikvision import HikvisionFingerprint
from camera_probe.infrastructure.fingerprints.axis import AxisFingerprint
from camera_probe.infrastructure.fingerprints.uniview import UniviewFingerprint
from camera_probe.infrastructure.fingerprints.xiongmai import XiongmaiFingerprint
from camera_probe.infrastructure.fingerprints.generic import GenericRTSPFingerprint

logger = logging.getLogger(__name__)


class FingerprintRegistry:
    """
    Registry of all known fingerprints.
    Order matters: strongest → weakest.
    """

    def __init__(self) -> None:
        self._fingerprints: list[Fingerprint] = [
            # ── STRONG VENDORS ───────────────────────────
            DahuaFingerprint(),
            HikvisionFingerprint(),
            AxisFingerprint(),
            UniviewFingerprint(),
            XiongmaiFingerprint(),

            # ── FALLBACK ─────────────────────────────────
            GenericRTSPFingerprint(),
        ]

    def match(self, evidence: dict[str, Any]) -> Optional[Fingerprint]:
        for fp in self._fingerprints:
            logger.trace("Trying fingerprint: %s", fp.__class__.__name__)
            try:
                if fp.match(evidence):
                    logger.debug(
                        "Fingerprint matched: %s → vendor=%s confidence=%.2f",
                        fp.__class__.__name__,
                        fp.vendor(),
                        fp.confidence(),
                    )
                    return fp
            except Exception as e:
                logger.warning(
                    "Fingerprint %s failed: %s",
                    fp.__class__.__name__,
                    e,
                )

        return None
