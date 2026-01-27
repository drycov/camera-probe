
from __future__ import annotations

import logging
from typing import Optional, ClassVar

from camera_probe.clients.registry import ClientRegistry
from camera_probe.infrastructure.http.client import HttpClient

logger = logging.getLogger(__name__)


@ClientRegistry.register
class HikvisionIsapiClient:
    vendor: ClassVar[str] = "hikvision"

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
        )
        self.http.set_auth(username, password)

        logger.debug(
            "hikvision client init | ip=%s | timeout=%.1fs",
            ip,
            timeout,
        )

    # ─────────────────────────────────────────────
    # Base URL
    # ─────────────────────────────────────────────

    async def _ensure_base_url(self) -> Optional[str]:
        return await self.http.get_base_url(
            test_paths=(
                "/ISAPI/System/deviceInfo",
                "/ISAPI/System/time",
                "/ISAPI/System/capabilities",
            ),
            ok_statuses=(200, 401, 403),
        )

    # ─────────────────────────────────────────────
    # Raw fetchers (NO parsing)
    # ─────────────────────────────────────────────

    async def get_device_info_raw(self) -> Optional[str]:
        base = await self._ensure_base_url()
        if not base:
            return None

        return await self.http.get(
            "/ISAPI/System/deviceInfo",
            base_url=base,
        )

    async def get_network_info_raw(self) -> Optional[str]:
        base = await self._ensure_base_url()
        if not base:
            return None

        for path in (
            "/ISAPI/System/Network/interfaces",
            "/ISAPI/System/Network/Interfaces",
            "/ISAPI/System/Network/Interfaces/1",
            "/ISAPI/Network/interfaces",
        ):
            raw = await self.http.get(path, base_url=base, force_basic=True)
            if raw:
                return raw

        return None

    # ─────────────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────────────

    def close(self) -> None:
        self.http.close()
