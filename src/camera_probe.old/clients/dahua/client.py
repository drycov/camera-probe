from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional, Any, ClassVar
from urllib.parse import urljoin

import aiohttp
import requests
from requests.auth import HTTPDigestAuth, HTTPBasicAuth

from camera_probe.clients.base import BaseClient
from camera_probe.clients.registry import ClientRegistry

logger = logging.getLogger(__name__)


@ClientRegistry.register
class DahuaCgiClient(BaseClient):
    """
    Dahua CGI client (Digest-first).

    Responsibilities:
    - determine base URL (http / https)
    - execute CGI requests (Digest → Basic fallback)
    - parse key=value responses
    - expose small, factual async API
    """

    vendor: ClassVar[str] = "dahua"

    def __init__(
        self,
        ip: str,
        *,
        username: str = "",
        password: str = "",
        timeout: float = 7.0,
        prefer_https: bool = False,
    ) -> None:
        super().__init__(
            ip=ip,
            timeout=timeout,
            prefer_https=prefer_https,
            verify_ssl=False,
        )

        self.username = username
        self.password = password

        self._digest = HTTPDigestAuth(username, password)
        self._basic = HTTPBasicAuth(username, password)

        logger.debug(
            "dahua client init | ip=%s | timeout=%.1fs | https=%s",
            self.ip,
            timeout,
            prefer_https,
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
                    "/cgi-bin/magicBox.cgi?action=getVendor",
                    "/cgi-bin/magicBox.cgi?action=getDeviceType",
                    "/cgi-bin/configManager.cgi?action=getConfig&name=Network",
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
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        url = urljoin(base, path)

        try:
            # 1) Digest (primary)
            r = requests.get(
                url,
                params=params,
                auth=self._digest,
                timeout=self.timeout,
                verify=False,
            )
            if r.status_code == 200:
                return r.text

            # 2) Basic fallback (OEM / old firmware)
            if r.status_code == 401:
                r = requests.get(
                    url,
                    params=params,
                    auth=self._basic,
                    timeout=self.timeout,
                    verify=False,
                )
                if r.status_code == 200:
                    return r.text

            logger.debug(
                "dahua non-200 | ip=%s | path=%s | status=%d",
                self.ip,
                path,
                r.status_code,
            )
            return None

        except Exception as exc:
            logger.debug(
                "dahua request failed | ip=%s | path=%s | error=%s",
                self.ip,
                path,
                type(exc).__name__,
            )
            return None

    # ──────────────────────────────────────────────
    # Async wrapper
    # ──────────────────────────────────────────────

    async def _get(
        self,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        base = await self._get_base_url()
        if not base:
            return None

        return await asyncio.to_thread(
            self._request_sync,
            base,
            path,
            params=params,
        )

    # ──────────────────────────────────────────────
    # Parsing helpers
    # ──────────────────────────────────────────────

    @staticmethod
    def _parse_kv(text: Optional[str]) -> Dict[str, str]:
        if not text:
            return {}

        out: Dict[str, str] = {}

        for line in text.splitlines():
            line = line.strip()
            if not line or "=" not in line:
                continue

            if line.startswith("var "):
                line = line[4:].strip()

            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"')

        return out

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    async def get_vendor(self) -> Optional[str]:
        text = await self._get("/cgi-bin/magicBox.cgi?action=getVendor")
        return self._parse_kv(text).get("vendor")

    async def get_device_type(self) -> Optional[str]:
        text = await self._get("/cgi-bin/magicBox.cgi?action=getDeviceType")
        return self._parse_kv(text).get("type")

    async def get_serial(self) -> Optional[str]:
        text = await self._get("/cgi-bin/magicBox.cgi?action=getSerialNo")
        kv = self._parse_kv(text)
        return kv.get("sn") or kv.get("serial") or kv.get("serialNumber")

    async def get_software_version(self) -> Optional[str]:
        text = await self._get("/cgi-bin/magicBox.cgi?action=getSoftwareVersion")
        return self._parse_kv(text).get("version")

    async def get_hardware_version(self) -> Optional[str]:
        text = await self._get("/cgi-bin/magicBox.cgi?action=getHardwareVersion")
        return self._parse_kv(text).get("version")

    # ──────────────────────────────────────────────
    # Unified client contract
    # ──────────────────────────────────────────────

    async def get_firmware(self) -> Optional[str]:
        """
        Unified firmware accessor for adapters.

        Priority:
        1. Software version (primary firmware identifier)
        2. Hardware version (fallback, if software missing)
        """
        try:
            sw = await self.get_software_version()
            if sw:
                return sw
        except Exception:
            pass

        try:
            hw = await self.get_hardware_version()
            if hw:
                return hw
        except Exception:
            pass

        return None

    async def get_network_info(self) -> Optional[Dict[str, Any]]:
        text = await self._get(
            "/cgi-bin/configManager.cgi",
            params={"action": "getConfig", "name": "Network"},
        )
        kv = self._parse_kv(text)
        if not kv:
            return None

        ip = kv.get("table.Network.eth0.IPAddress")
        mask = kv.get("table.Network.eth0.SubnetMask")
        gateway = kv.get("table.Network.eth0.DefaultGateway")
        mac = kv.get("table.Network.eth0.PhysicalAddress")

        cidr = None
        gateway_in_subnet = None

        if ip and mask:
            try:
                import ipaddress

                net = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
                cidr = net.prefixlen
                if gateway:
                    gateway_in_subnet = ipaddress.IPv4Address(gateway) in net
            except Exception:
                pass

        return {
            "ip": ip,
            "mask": mask,
            "cidr": cidr,
            "gateway": gateway,
            "gateway_in_subnet": gateway_in_subnet,
            "mac": mac.upper().replace("-", ":") if mac else None,
        }

    async def get_ntp_info(self) -> Optional[Dict[str, str]]:
        text = await self._get(
            "/cgi-bin/configManager.cgi",
            params={"action": "getConfig", "name": "NTP"},
        )
        return self._parse_kv(text)

    async def get_mac(self) -> Optional[str]:
        info = await self.get_network_info()
        return info.get("mac") if info else None
