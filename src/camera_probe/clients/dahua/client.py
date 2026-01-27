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
    Dahua CGI client.

    Transport-only:
    - HTTP only
    - returns RAW responses (str)
    - no parsing
    - no domain models
    """

    vendor: ClassVar[str] = "dahua"

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

        self.http = HttpClient(
            ip=ip,
            timeout=timeout,
            prefer_https=prefer_https,
            verify_ssl=verify_ssl,
            try_anonymous=True,
        )
        self.http.set_auth(username, password)

        logger.debug("dahua client init | ip=%s", ip)

    # ─────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────

    def close(self) -> None:
        self.http.close()

    # ─────────────────────────────────────
    # Base URL
    # ─────────────────────────────────────

    async def _ensure_base_url(self) -> Optional[str]:
        return await self.http.get_base_url(
            test_paths=(
                "/cgi-bin/magicBox.cgi?action=getSystemInfo",
                "/cgi-bin/main-cgi?action=getDeviceInfo",
                "/cgi-bin/global.cgi?action=getCurrentTime",
            ),
            ok_statuses=(200, 401, 403),
        )

    # ─────────────────────────────────────
    # Public API (DEVICE)
    # ─────────────────────────────────────

    async def get_device_info(self) -> Optional[str]:
        """
        Returns RAW device info (CGI text).
        """
        base = await self._ensure_base_url()
        raw = await self.http.get(
            "/cgi-bin/magicBox.cgi?action=getSystemInfo",
            base_url=base,
        )
        
        logger.error(raw)

        if not raw:
            raw = await self.http.get(
                "/cgi-bin/main-cgi?action=getDeviceInfo",
                base_url=base,
                force_basic=True,
            )

        return raw

    async def get_software_version(self) -> Optional[str]:
        """
        Returns RAW software version (CGI text).
        """
        base = await self._ensure_base_url()
        if not base:
            return None
        
        raw = await self.http.get(
            "/cgi-bin/magicBox.cgi?action=getSoftwareVersion",
            base_url=base,
        )
        
        logger.error(raw)

        return raw

    # ─────────────────────────────────────
    # Public API (NETWORK)
    # ─────────────────────────────────────

    async def get_network_info(self) -> Optional[str]:
        """
        Returns RAW network config (CGI text).
        """
        base = await self._ensure_base_url()
        if not base:
            return None

        raw = await self.http.get(
            "/cgi-bin/configManager.cgi?action=getConfig&name=Network",
            base_url=base,
            force_basic=True,
        )

        logger.error(raw)

        return raw
