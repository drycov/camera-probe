# camera_probe/infrastructure/device/dahua.py

from __future__ import annotations

import html
import logging
import re
from typing import Optional, Dict

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

        model = data.get("devicetype") or data.get("type") or data.get("model")

        serial = data.get("sn") or data.get("serialno") or data.get("serialnumber")

        firmware = (
            data.get("version")
            or data.get("softwareversion")
            or data.get("firmwareversion")
        )
        # logger.trace(firmware)

        mac = data.get("mac") or data.get("macaddress")
        mac = mac.upper() if mac else None

        if not any([model, serial, mac, firmware]):
            return self._extract_from_web_text(raw)

        return {
            "model": model,
            "serial": serial,
            "mac": mac,
            "firmware": firmware,
            "manufacturer": "Dahua",
        }

    def _extract_from_web_text(self, raw: str) -> Optional[Dict[str, Optional[str]]]:
        text = self._normalize_web_text(raw)

        model = self._search_label(
            text,
            "Device Type",
            "Тип",
        )
        serial = self._search_label(
            text,
            "S/N",
        )
        firmware = self._search_label(
            text,
            "System Version",
            "Версия системы",
        )

        if not any([model, serial, firmware]):
            logger.debug("dahua device extractor: no meaningful fields")
            return None

        return {
            "model": model,
            "serial": serial,
            "mac": None,
            "firmware": firmware,
            "manufacturer": "Dahua",
        }

    @staticmethod
    def _normalize_web_text(raw: str) -> str:
        text = re.sub(r"<[^>]+>", " ", raw)
        text = html.unescape(text)
        text = text.replace("\xa0", " ")
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _search_label(text: str, *labels: str) -> Optional[str]:
        for label in labels:
            pattern = rf"{re.escape(label)}\s*[:：]?\s*(.+?)(?=\s+(?:[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*|[А-ЯЁ][а-яё]+(?:\s+[а-яё]+)*|S/N)\s*[:：]?\s*|$)"
            match = re.search(pattern, text)
            if match:
                value = match.group(1).strip(" :,")
                if value:
                    return value
        return None

    # ─────────────────────────────
    # Unused capabilities (null)
    # ─────────────────────────────

    def extract_network(self, raw: str) -> Optional[NetworkInfo]:
        return None

    def extract_ntp(self, raw: str) -> Optional[NtpInfo]:
        return None
