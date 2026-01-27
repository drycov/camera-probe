# camera_probe/infrastructure/device/hikvision.py

from __future__ import annotations

import logging
from typing import Optional, Dict
from xml.etree import ElementTree as ET

from camera_probe.infrastructure.device.decorators import register_device_extractor

logger = logging.getLogger(__name__)


@register_device_extractor("hikvision")
class HikvisionDeviceExtractor:
    """
    Extracts device information from Hikvision ISAPI XML.

    Input:
      raw XML string

    Output (normalized dict):
      {
        model,
        serial,
        mac,
        firmware,
        manufacturer
      }
    """

    NS = {
        "ns": "http://www.hikvision.com/ver20/XMLSchema"
    }

    def extract(self, raw: str) -> Optional[Dict[str, str]]:
        if not raw:
            return None

        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            logger.debug("hikvision device xml parse failed")
            return None

        def _find(*tags: str) -> Optional[str]:
            for tag in tags:
                # 1️⃣ namespaced
                el = root.find(f".//ns:{tag}", self.NS)
                if el is not None and el.text:
                    return el.text.strip()

                # 2️⃣ fallback without namespace
                for node in root.iter():
                    if node.tag.lower().endswith(tag.lower()) and node.text:
                        return node.text.strip()
            return None

        model = _find("model")
        serial = _find("serialNumber")
        mac = _find("macAddress", "MACAddress")
        firmware = _find("firmwareVersion", "softwareVersion")
        manufacturer = _find("manufacturer")

        if not any([model, serial, mac]):
            logger.debug("hikvision device extractor empty result")
            return None

        return {
            "model": model,
            "serial": serial,
            "mac": mac.upper().replace("-", ":") if mac else None,
            "firmware": firmware,
            "manufacturer": manufacturer or "Hikvision",
        }
