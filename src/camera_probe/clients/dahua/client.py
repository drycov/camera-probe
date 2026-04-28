# camera_probe/clients/dahua/client.py

from __future__ import annotations

import logging
from typing import ClassVar, Optional

from camera_probe.clients.registry import ClientRegistry
from camera_probe.infrastructure.http.client import HttpClient

logger = logging.getLogger(__name__)


@ClientRegistry.register
class DahuaCgiClient:
    """
    Dahua CGI client (transport-only).

    Responsibilities:
    - HTTP transport
    - auth handling
    - RAW CGI responses
    """

    vendor: ClassVar[str] = "dahua"

    _BASE_TEST_PATHS = (
        "/cgi-bin/magicBox.cgi?action=getSystemInfo",
        "/cgi-bin/main-cgi?action=getDeviceInfo",
        "/cgi-bin/global.cgi?action=getCurrentTime",
    )

    def __init__(
        self,
        ip: str,
        *,
        username: str,
        password: str,
        timeout: float = 5.0,
        prefer_https: bool = False,
        verify_ssl: bool = False,
    ) -> None:
        self.ip = ip
        self._base_url: Optional[str] = None

        self.http = HttpClient(
            ip=ip,
            timeout=timeout,
            prefer_https=prefer_https,
            verify_ssl=verify_ssl,
            try_anonymous=True,
        )
        self.http.set_auth(username, password)

        logger.debug("dahua client initialized | ip=%s", ip)

    # ─────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────

    def close(self) -> None:
        self.http.close()

    # ─────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────

    async def _get_base_url(self) -> Optional[str]:
        """
        Resolve and cache base URL once per client lifecycle.
        """
        if self._base_url:
            return self._base_url

        base = await self.http.get_base_url(
            test_paths=self._BASE_TEST_PATHS,
            ok_statuses=(200, 401, 403),
        )

        if not base:
            logger.debug("dahua base url not resolved | ip=%s", self.ip)
            return None

        self._base_url = base
        logger.debug("dahua base url resolved | ip=%s base=%s", self.ip, base)
        return base

    async def _get(
        self,
        path: str,
        *,
        allow_anonymous: bool = False,
        force_basic: bool = False,
    ) -> Optional[str]:
        base = await self._get_base_url()
        if not base:
            return None

        return await self.http.get(
            path,
            base_url=base,
            allow_anonymous=allow_anonymous,
            force_basic=force_basic,
        )

    # ─────────────────────────────────────
    # Public API (DEVICE)
    # ─────────────────────────────────────

    async def get_device_info(self) -> Optional[str]:
        """
        RAW device info (CGI text).
        """
        raw = await self._get(
            "/cgi-bin/magicBox.cgi?action=getSystemInfo",
        )

        if raw:
            return raw

        raw = await self._get(
            "/cgi-bin/main-cgi?action=getDeviceInfo",
            force_basic=True,
        )
        if raw:
            return raw

        fallback_parts = []

        device_type = await self.get_device_type()
        if device_type:
            fallback_parts.append(device_type)

        serial_no = await self.get_serial_no()
        if serial_no:
            fallback_parts.append(serial_no)

        if fallback_parts:
            return "\n".join(fallback_parts)

        return None

    async def get_software_version(self) -> Optional[str]:
        """
        RAW software version (CGI text).
        """
        return await self._get(
            "/cgi-bin/magicBox.cgi?action=getSoftwareVersion",
        )

    async def get_device_type(self) -> Optional[str]:
        return await self._get(
            "/cgi-bin/magicBox.cgi?action=getDeviceType",
            force_basic=True,
        )

    async def get_serial_no(self) -> Optional[str]:
        return await self._get(
            "/cgi-bin/magicBox.cgi?action=getSerialNo",
            force_basic=True,
        )

    # ─────────────────────────────────────
    # Public API (NETWORK)
    # ─────────────────────────────────────

    async def get_network_info(self) -> Optional[str]:
        """
        RAW network config (CGI text).
        """
        return await self._get(
            "/cgi-bin/configManager.cgi?action=getConfig&name=Network",
            force_basic=True,
        )
