# camera_probe/infrastructure/device/dahua.py

from __future__ import annotations

import logging
from typing import Optional, Dict

from camera_probe.domain.ports.device_extractor import DeviceExtractor
from camera_probe.domain.models.network_info import NetworkInfo
from camera_probe.domain.models.ntp_info import NtpInfo
from camera_probe.infrastructure.device.decorators import register_device_extractor

logger = logging.getLogger(__name__)


@register_device_extractor("dahua")
class DahuaDeviceExtractor:
    """
    Extracts device information from Dahua CGI (key=value).

    Output keys:
      model
      serial
      mac
      firmware
      manufacturer
    """

    def extract(self, raw: str) -> Optional[Dict[str, Optional[str]]]:
        if not raw:
            return None

        logger.trace("dahua device raw:\n%s", raw)

        data: Dict[str, str] = {}

        for line in raw.splitlines():
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip().lower()] = v.strip()

        # ─────────────────────────────
        # Normalization
        # ─────────────────────────────

        model = data.get("devicetype") or data.get("model")

        serial = data.get("serialno") or data.get("serialnumber")

        firmware = (
            data.get("version")
            or data.get("softwareversion")
            or data.get("firmwareversion")
        )
        # logger.trace(firmware)

        mac = data.get("mac") or data.get("macaddress")
        mac = mac.upper() if mac else None

        if not any([model, serial, mac, firmware]):
            logger.debug("dahua device extractor: no meaningful fields")
            return None

        return {
            "model": model,
            "serial": serial,
            "mac": mac,
            "firmware": firmware,
            "manufacturer": "Dahua",
        }

    # ─────────────────────────────
    # Unused capabilities (null)
    # ─────────────────────────────

    def extract_network(self, raw: str) -> Optional[NetworkInfo]:
        return None

    def extract_ntp(self, raw: str) -> Optional[NtpInfo]:
        return None
