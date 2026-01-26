from __future__ import annotations

import logging
from typing import Dict, Optional, ClassVar
from xml.etree import ElementTree as ET

from camera_probe.clients.registry import ClientRegistry
from camera_probe.infrastructure.http.client import HttpClient

logger = logging.getLogger(__name__)


@ClientRegistry.register
class HikvisionIsapiClient:
    """
    Hikvision ISAPI client.

    Characteristics:
    - Digest → Basic → Anonymous handled by HttpClient
    - tolerant to 401 (expected Hikvision behavior)
    - async API
    - no direct dependency on requests / aiohttp
    """

    vendor: ClassVar[str] = "hikvision"

    ISAPI_PATHS = (
        "/ISAPI/System/deviceInfo",
        "/ISAPI/System/time",
        "/ISAPI/System/capabilities",
    )

    def __init__(
        self,
        ip: str,
        *,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 7.0,
        prefer_https: bool = False,
        try_anonymous: bool = False,
        verify_ssl: bool = False,
    ) -> None:
        self.ip = ip

        self.http = HttpClient(
            ip=ip,
            timeout=timeout,
            prefer_https=prefer_https,
            try_anonymous=try_anonymous,
            verify_ssl=verify_ssl,
        )
        self.http.set_auth(username, password)

        self._base_ready = False

        logger.debug(
            "hikvision isapi client init | ip=%s | timeout=%.1fs | https=%s | anon=%s",
            ip,
            timeout,
            prefer_https,
            try_anonymous,
        )

    # ──────────────────────────────────────────────
    # Base URL
    # ──────────────────────────────────────────────

    async def _ensure_base(self) -> bool:
        if self._base_ready:
            return True

        base = await self.http.get_base_url(
            test_paths=self.ISAPI_PATHS,
            ok_statuses=(200, 401, 403),
        )

        if not base:
            logger.debug("hikvision base url not detected | ip=%s", self.ip)
            return False

        self._base_ready = True
        return True

    # ──────────────────────────────────────────────
    # XML helpers
    # ──────────────────────────────────────────────

    @staticmethod
    def _parse_xml(text: str) -> Optional[ET.Element]:
        try:
            return ET.fromstring(text)
        except ET.ParseError:
            return None

    @staticmethod
    def _extract_text(
        root: ET.Element,
        tag: str,
        default: Optional[str] = None,
    ) -> Optional[str]:
        tag = tag.lower()
        for el in root.iter():
            if el.tag.lower().endswith(tag) and el.text:
                return el.text.strip()
        return default

    # ──────────────────────────────────────────────
    # Core ISAPI fetch
    # ──────────────────────────────────────────────

    async def _get_xml(
        self,
        path: str,
        *,
        allow_anonymous: bool = False,
        force_basic: bool = False,
    ) -> Optional[ET.Element]:

        if not await self._ensure_base():
            return None

        text = await self.http.get(
            path,
            allow_anonymous=allow_anonymous,
            force_basic=force_basic,
        )

        if not text:
            logger.debug(
                "hikvision empty response | ip=%s | path=%s",
                self.ip,
                path,
            )
            return None

        xml = self._parse_xml(text)
        if not xml:
            logger.warning(
                "hikvision invalid xml | ip=%s | path=%s",
                self.ip,
                path,
            )
        return xml

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    async def get_device_info(self) -> Dict[str, Optional[str]]:
        logger.debug("hikvision get_device_info | ip=%s", self.ip)

        root = await self._get_xml(
            "/ISAPI/System/deviceInfo",
            allow_anonymous=False,
        )

        if root is None:
            logger.info("hikvision deviceInfo unavailable | ip=%s", self.ip)
            return {}

        data = {
            "model": self._extract_text(root, "model"),
            "serial": self._extract_text(root, "serialnumber"),
            "mac": self._extract_text(root, "macaddress"),
            "firmware": (
                self._extract_text(root, "firmwareversion")
                or self._extract_text(root, "softwareversion")
            ),
            "manufacturer": self._extract_text(root, "manufacturer"),
        }

        return {k: v for k, v in data.items() if v}

    async def get_model(self) -> Optional[str]:
        return (await self.get_device_info()).get("model")

    async def get_serial(self) -> Optional[str]:
        return (await self.get_device_info()).get("serial")

    async def get_mac(self) -> Optional[str]:
        mac = (await self.get_device_info()).get("mac")
        return mac.upper().replace("-", ":") if mac else None

    async def get_firmware(self) -> Optional[str]:
        return (await self.get_device_info()).get("firmware")
