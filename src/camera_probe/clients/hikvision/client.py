from __future__ import annotations

import logging
from typing import Optional, ClassVar

from camera_probe.clients.registry import ClientRegistry
from camera_probe.infrastructure.http.client import HttpClient

logger = logging.getLogger(__name__)

BASE_TEST_PATHS = (
    "/ISAPI/System/deviceInfo",
    "/ISAPI/System/time",
    "/ISAPI/System/capabilities",
)

DEVICE_INFO_PATHS = (
    "/ISAPI/System/deviceInfo",
)

NETWORK_INFO_PATHS = (
    "/ISAPI/System/Network/bond",
    "/ISAPI/System/Network/interfaces",
    "/ISAPI/System/Network/Interfaces",
    "/ISAPI/System/Network/Interfaces/1",
    "/ISAPI/Network/interfaces",
)


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
        self._base_url: Optional[str] = None
        self._last_device_info_path: Optional[str] = None
        self._last_network_info_path: Optional[str] = None

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
        if self._base_url is not None:
            return self._base_url

        self._base_url = await self.http.get_base_url(
            test_paths=BASE_TEST_PATHS,
            ok_statuses=(200, 401, 403),
        )
        return self._base_url

    async def _get_first(
        self,
        paths: tuple[str, ...],
        *,
        force_basic: bool = False,
        purpose: str | None = None,
    ) -> Optional[str]:
        base = await self._ensure_base_url()
        if not base:
            logger.debug("hikvision base url unavailable | ip=%s", self.ip)
            return None

        for path in paths:
            raw = await self.http.get(
                path,
                base_url=base,
                force_basic=force_basic,
            )
            if raw:
                if purpose == "device":
                    self._last_device_info_path = path
                elif purpose == "network":
                    self._last_network_info_path = path
                logger.debug(
                    "hikvision endpoint resolved | ip=%s | path=%s",
                    self.ip,
                    path,
                )
                return raw

        logger.debug(
            "hikvision endpoints exhausted | ip=%s | paths=%s",
            self.ip,
            list(paths),
        )
        return None

    # ─────────────────────────────────────────────
    # Raw fetchers (NO parsing)
    # ─────────────────────────────────────────────

    async def get_device_info_raw(self) -> Optional[str]:
        return await self._get_first(
            DEVICE_INFO_PATHS,
            purpose="device",
        )

    async def get_network_info_raw(self) -> Optional[str]:
        return await self._get_first(
            NETWORK_INFO_PATHS,
            force_basic=True,
            purpose="network",
        )

    # ─────────────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────────────

    def close(self) -> None:
        self.http.close()
