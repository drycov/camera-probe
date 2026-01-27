# from __future__ import annotations

# import logging
# from typing import Dict, Optional, ClassVar
# from xml.etree import ElementTree as ET

# from camera_probe.clients.registry import ClientRegistry
# from camera_probe.infrastructure.http.client import HttpClient

# logger = logging.getLogger(__name__)


# @ClientRegistry.register
# class HikvisionIsapiClient:
#     """
#     Hikvision ISAPI client.

#     Transport:
#     - HttpClient (requests.Session + DigestAuth)
#     """

#     vendor: ClassVar[str] = "hikvision"

#     def __init__(
#         self,
#         ip: str,
#         *,
#         username: str,
#         password: str,
#         timeout: float = 5.0,
#         prefer_https: bool = False,
#         verify_ssl: bool = False,
#     ) -> None:
#         self.ip = ip

#         self.http = HttpClient(
#             ip=ip,
#             timeout=timeout,
#             prefer_https=prefer_https,
#             verify_ssl=verify_ssl,
#         )

#         self.http.set_auth(username, password)

#         logger.debug(
#             "hikvision client init | ip=%s | timeout=%.1fs",
#             ip,
#             timeout,
#         )

#     # ─────────────────────────────────────────────
#     # Helpers
#     # ─────────────────────────────────────────────

#     @staticmethod
#     def _parse_xml(text: str) -> Optional[ET.Element]:
#         try:
#             return ET.fromstring(text)
#         except ET.ParseError:
#             return None

#     @staticmethod
#     def _extract(root: ET.Element, tag: str) -> Optional[str]:
#         tag = tag.lower()
#         for el in root.iter():
#             if el.tag.lower().endswith(tag) and el.text:
#                 return el.text.strip()
#         return None

#     # ─────────────────────────────────────────────
#     # Base URL
#     # ─────────────────────────────────────────────

#     async def _ensure_base_url(self) -> Optional[str]:
#         return await self.http.get_base_url(
#             test_paths=(
#                 "/ISAPI/System/deviceInfo",
#                 "/ISAPI/System/time",
#                 "/ISAPI/System/capabilities",
#             ),
#             ok_statuses=(200, 401, 403),
#         )

#     # ─────────────────────────────────────────────
#     # Public API
#     # ─────────────────────────────────────────────

#     async def get_device_info(self) -> Dict[str, str]:
#         logger.debug("hikvision get_device_info | ip=%s", self.ip)

#         base = await self._ensure_base_url()
#         if not base:
#             logger.info("hikvision base_url unavailable | ip=%s", self.ip)
#             return {}

#         xml_text = await self.http.get(
#             "/ISAPI/System/deviceInfo",
#             base_url=base,
#         )

#         if not xml_text:
#             logger.info("hikvision deviceInfo unavailable | ip=%s", self.ip)
#             return {}

#         root = self._parse_xml(xml_text)
#         if not root:
#             logger.warning("hikvision invalid XML | ip=%s", self.ip)
#             return {}

#         data = {
#             "model": self._extract(root, "model"),
#             "serial": self._extract(root, "serialnumber"),
#             "mac": self._extract(root, "macaddress"),
#             "firmware": (
#                 self._extract(root, "firmwareversion")
#                 or self._extract(root, "softwareversion")
#             ),
#             "manufacturer": self._extract(root, "manufacturer"),
#         }

#         return {k: v for k, v in data.items() if v}

#     # camera_probe/clients/hikvision/client.py

#     async def _get_network_raw(self) -> Optional[str]:
#         for path in (
#             "/ISAPI/System/Network/interfaces",
#             "/ISAPI/System/Network/Interfaces",
#             "/ISAPI/System/Network/Interfaces/1",
#             "/ISAPI/Network/interfaces",
#         ):
#             raw = await self._get(path, force_basic=True)
#             if raw:
#                 return raw
#         return None

#     # ─────────────────────────────────────────────
#     # Lifecycle
#     # ─────────────────────────────────────────────

#     def close(self) -> None:
#         self.http.close()

# camera_probe/clients/hikvision/client.py
