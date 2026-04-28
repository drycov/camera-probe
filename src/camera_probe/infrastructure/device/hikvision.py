from __future__ import annotations

import logging
from typing import Optional, Dict
from xml.etree.ElementTree import Element

from camera_probe.infrastructure.device.decorators import register_device_extractor
from camera_probe.infrastructure.xml.parser import parse_xml

logger = logging.getLogger(__name__)


@register_device_extractor("hikvision")
class HikvisionDeviceExtractor:
    """
    Extracts device information from Hikvision ISAPI XML.
    """

    def extract(self, raw: str) -> Optional[Dict[str, str]]:
        root = parse_xml(raw)
        if root is None:
            return None

        NS = self._extract_ns(root)

        model = self._find(root, NS, "model")
        raw_serial = self._find(root, NS, "serialNumber")
        sub_serial = self._find(root, NS, "subSerialNumber")
        serial = self._normalize_serial(
            model=model,
            serial=raw_serial,
            sub_serial=sub_serial,
        )
        mac = self._find(root, NS, "macAddress", "MACAddress")
        firmware = self._find(root, NS, "firmwareVersion", "softwareVersion")
        manufacturer = self._find(root, NS, "manufacturer") or "Hikvision"

        if not any([model, serial, mac]):
            logger.debug("hikvision device extractor empty result")
            return None

        return {
            "model": model,
            "serial": serial,
            "mac": mac.upper().replace("-", ":") if mac else None,
            "firmware": firmware,
            "manufacturer": manufacturer,
        }

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    @staticmethod
    def _extract_ns(root: Element) -> dict[str, str]:
        """
        Extract default XML namespace if present.
        """
        if root.tag.startswith("{"):
            uri = root.tag.split("}")[0][1:]
            return {"ns": uri}
        return {}

    @staticmethod
    def _find(root: Element, ns: dict[str, str], *tags: str) -> Optional[str]:
        for tag in tags:
            # 1️⃣ namespaced lookup
            if ns:
                el = root.find(f".//ns:{tag}", ns)
                if el is not None and el.text:
                    return el.text.strip()

            # 2️⃣ fallback without namespace
            el = root.find(f".//{tag}")
            if el is not None and el.text:
                return el.text.strip()

        return None

    @staticmethod
    def _normalize_serial(
        *,
        model: Optional[str],
        serial: Optional[str],
        sub_serial: Optional[str],
    ) -> Optional[str]:
        if not serial:
            return sub_serial.strip() if sub_serial else None

        normalized = serial.strip()
        if model and normalized.startswith(model):
            suffix = normalized[len(model):].strip(" -")
            if suffix:
                return suffix

        if normalized:
            return normalized

        return sub_serial.strip() if sub_serial else None
