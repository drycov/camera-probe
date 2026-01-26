from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional, Any, ClassVar
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

import aiohttp
import requests
from requests.auth import HTTPDigestAuth, HTTPBasicAuth

from camera_probe.clients.base import BaseClient
from camera_probe.clients.registry import ClientRegistry

logger = logging.getLogger(__name__)


@ClientRegistry.register
class HikvisionIsapiClient(BaseClient):
    """
    Hikvision ISAPI client (Digest-first).

    Responsibilities:
    - determine base URL (http/https) via BaseClient
    - perform ISAPI requests (Digest → Basic fallback)
    - parse XML responses
    - expose small, factual async API
    """

    vendor: ClassVar[str] = "hikvision"

    def __init__(
        self,
        ip: str,
        *,
        username: str = "",
        password: str = "",
        timeout: float = 7.0,
        prefer_https: bool = False,
        try_anonymous: bool = True,
        verify_ssl: bool = False,
    ) -> None:
        super().__init__(
            ip=ip,
            timeout=timeout,
            prefer_https=prefer_https,
            verify_ssl=verify_ssl,
        )

        self.username = username
        self.password = password
        self.try_anonymous = try_anonymous

        self._digest = HTTPDigestAuth(username, password)
        self._basic = HTTPBasicAuth(username, password)

        logger.debug(
            "hikvision client init | ip=%s | timeout=%.1fs | https=%s | anon=%s",
            self.ip,
            timeout,
            prefer_https,
            try_anonymous,
        )

    # ──────────────────────────────────────────────
    # Base URL
    # ──────────────────────────────────────────────

    async def _get_base_url(self) -> Optional[str]:
        if self._base_valid():
            return self._base_url

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        ) as session:
            return await self.discover_base_url(
                session,
                test_paths=[
                    "/ISAPI/System/deviceInfo",
                    "/ISAPI/System/time",
                    "/ISAPI/System/capabilities",
                ],
                ok_statuses=(200, 401),
            )

    # ──────────────────────────────────────────────
    # Sync HTTP (requests)
    # ──────────────────────────────────────────────

    def _request_sync(
        self,
        base: str,
        path: str,
        *,
        allow_anonymous: bool = False,
        force_basic: bool = False,
    ) -> Optional[str]:
        url = urljoin(base, path)

        try:
            # 0) Anonymous (optional)
            if allow_anonymous and self.try_anonymous:
                r = requests.get(
                    url,
                    timeout=self.timeout,
                    verify=self.verify_ssl,
                )
                if r.status_code == 200:
                    return r.text

            # 1) Digest (primary)
            r = requests.get(
                url,
                auth=self._digest,
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
            if r.status_code == 200:
                return r.text

            # 2) Basic fallback
            if r.status_code == 401 or force_basic:
                r = requests.get(
                    url,
                    auth=self._basic,
                    timeout=self.timeout,
                    verify=self.verify_ssl,
                )
                if r.status_code == 200:
                    return r.text

            logger.debug(
                "hikvision non-200 | ip=%s | path=%s | status=%d",
                self.ip,
                path,
                r.status_code,
            )
            return None

        except Exception as exc:
            logger.debug(
                "hikvision request failed | ip=%s | path=%s | error=%s",
                self.ip,
                path,
                type(exc).__name__,
            )
            return None

    # ──────────────────────────────────────────────
    # Async XML wrapper
    # ──────────────────────────────────────────────

    async def _get_xml(
        self,
        path: str,
        *,
        allow_anonymous: bool = False,
        force_basic: bool = False,
    ) -> Optional[ET.Element]:
        base = await self._get_base_url()
        if not base:
            return None

        text = await asyncio.to_thread(
            self._request_sync,
            base,
            path,
            allow_anonymous=allow_anonymous,
            force_basic=force_basic,
        )

        if not text:
            return None

        try:
            return ET.fromstring(text)
        except ET.ParseError:
            logger.warning(
                "hikvision invalid xml | ip=%s | path=%s",
                self.ip,
                path,
            )
            return None

    # ──────────────────────────────────────────────
    # XML helpers
    # ──────────────────────────────────────────────

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
    # Public API
    # ──────────────────────────────────────────────

    async def get_device_info(self) -> Dict[str, Optional[str]]:
        logger.debug("hikvision get_device_info | ip=%s", self.ip)

        root = await self._get_xml(
            "/ISAPI/System/deviceInfo",
            allow_anonymous=True,
        )

        if root is None:
            logger.info("hikvision device_info unavailable | ip=%s", self.ip)
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

    async def get_serial(self) -> Optional[str]:
        return (await self.get_device_info()).get("serial")

    async def get_model(self) -> Optional[str]:
        return (await self.get_device_info()).get("model")

    async def get_mac(self) -> Optional[str]:
        mac = (await self.get_device_info()).get("mac")
        return mac.upper().replace("-", ":") if mac else None

    async def get_software_version(self) -> Optional[str]:
        return (await self.get_device_info()).get("firmware")

    async def get_network_info(self) -> Optional[Dict[str, Any]]:
        logger.debug("hikvision get_network_info | ip=%s", self.ip)

        root = None
        for path in (
            "/ISAPI/System/Network/interfaces",
            "/ISAPI/System/Network/Interfaces",
            "/ISAPI/System/Network/Interfaces/1",
            "/ISAPI/Network/interfaces",
        ):
            root = await self._get_xml(path, force_basic=True)
            if root is not None:
                break

        if root is None:
            return None

        NS = {"ns": "http://www.hikvision.com/ver20/XMLSchema"}

        iface = root.find(".//ns:NetworkInterface", NS)
        if iface is None:
            return None

        ip_node = iface.find(".//ns:IPAddress", NS)
        if ip_node is None:
            return None

        ip = ip_node.findtext("ns:ipAddress", namespaces=NS)
        mask = ip_node.findtext("ns:subnetMask", namespaces=NS)

        gw_node = ip_node.find("ns:DefaultGateway/ns:ipAddress", NS)
        gateway = gw_node.text if gw_node is not None else None

        mac = iface.findtext(".//ns:MACAddress", namespaces=NS)

        if not any([ip, mask, gateway]):
            return None

        cidr = None
        gateway_in_subnet = None
        if ip and mask:
            import ipaddress

            net = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
            cidr = net.prefixlen
            if gateway:
                gateway_in_subnet = ipaddress.IPv4Address(gateway) in net

        return {
            "ip": ip,
            "mask": mask,
            "cidr": cidr,
            "gateway": gateway,
            "gateway_in_subnet": gateway_in_subnet,
            "mac": mac.upper().replace("-", ":") if mac else None,
        }

    async def get_ntp_info(self) -> Optional[Dict[str, Any]]:
        logger.debug("hikvision get_ntp_info | ip=%s", self.ip)

        root = await self._get_xml("/ISAPI/System/time/ntpServers")
        if root is None:
            return None

        NS = {"ns": "http://www.hikvision.com/ver20/XMLSchema"}

        server = root.find(".//ns:NTPServer", NS)
        if server is None:
            return {
                "enabled": False,
                "server": None,
                "port": None,
                "interval": None,
            }

        ip = server.findtext("ns:ipAddress", namespaces=NS)
        port = server.findtext("ns:portNo", namespaces=NS)
        interval = server.findtext("ns:synchronizeInterval", namespaces=NS)

        return {
            "enabled": True,
            "server": ip,
            "port": int(port) if port else None,
            "interval": int(interval) if interval else None,
        }
