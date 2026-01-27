# camera_probe/infrastructure/device/dahua.py

from __future__ import annotations

import logging
from typing import Optional, Dict

from camera_probe.infrastructure.device.decorators import register_device_extractor

logger = logging.getLogger(__name__)


@register_device_extractor("dahua")
class DahuaDeviceExtractor:
    """
    Extracts device information from Dahua CGI (key=value).

    Input:
      raw CGI text

    Output:
      {
        model,
        serial,
        mac,
        firmware,
        manufacturer
      }
    """

    def extract(self, raw: str) -> Optional[Dict[str, str]]:
        logger.trace(raw)
        if not raw:
            return None

        data: Dict[str, str] = {}

        for line in raw.splitlines():
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip().lower()] = v.strip()

        # ─────────────────────────────
        # Normalization
        # ─────────────────────────────

        model = (
            data.get("devicetype")
            or data.get("model")
        )

        serial = (
            data.get("serialno")
            or data.get("serialnumber")
        )

        firmware = (
            data.get("version")
            or data.get("softwareversion")
            or data.get("firmwareversion")
        )

        # ⚠️ MAC чаще берётся из NetworkExtractor,
        # но если есть — используем
        mac = (
            data.get("mac")
            or data.get("macaddress")
        )

        if not any([model, serial, mac]):
            logger.debug("dahua device extractor empty result")
            return None

        return {
            "model": model,
            "serial": serial,
            "mac": mac.upper() if mac else None,
            "firmware": firmware,
            "manufacturer": "Dahua",
        }
