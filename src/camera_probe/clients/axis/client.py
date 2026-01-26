from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, ClassVar
from urllib.parse import urljoin

import aiohttp

from camera_probe.clients.base import BaseClient
from camera_probe.clients.registry import ClientRegistry

logger = logging.getLogger(__name__)


@ClientRegistry.register
class AxisVapixClient(BaseClient):
    """
    Async client for Axis VAPIX API.

    Responsibilities:
    - determine working base URL (http / https)
    - execute VAPIX HTTP requests via aiohttp
    - parse JSON responses
    - expose small, factual async API
    """

    vendor: ClassVar[str] = "axis"

    def __init__(
        self,
        ip: str,
        *,
        username: str = "",
        password: str = "",
        timeout: float = 6.0,
        prefer_https: bool = False,
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

        logger.debug(
            "axis client init | ip=%s | timeout=%.1fs | https=%s | auth=%s",
            self.ip,
            timeout,
            prefer_https,
            bool(username or password),
        )

    # ──────────────────────────────────────────────
    # Base URL
    # ──────────────────────────────────────────────

    async def _get_base_url(
        self,
        session: aiohttp.ClientSession,
    ) -> Optional[str]:
        if self._base_valid():
            return self._base_url

        return await self.discover_base_url(
            session,
            test_paths=[
                "/axis-cgi/basicdeviceinfo.cgi",
                "/axis-cgi/param.cgi?action=list",
                "/axis-cgi/time.cgi",
            ],
            ok_statuses=(200, 401),
        )

    # ──────────────────────────────────────────────
    # Low-level HTTP
    # ──────────────────────────────────────────────

    async def _get_json(
        self,
        session: aiohttp.ClientSession,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        base = await self._get_base_url(session)
        if not base:
            return None

        url = urljoin(base, path)

        try:
            async with session.get(
                url,
                params=params,
                ssl=self.verify_ssl,
            ) as resp:
                if resp.status != 200:
                    logger.debug(
                        "axis non-200 | ip=%s | path=%s | status=%d",
                        self.ip,
                        path,
                        resp.status,
                    )
                    return None

                return await resp.json(content_type=None)

        except json.JSONDecodeError:
            logger.warning(
                "axis invalid_json | ip=%s | url=%s",
                self.ip,
                url,
            )
            return None

        except Exception as exc:
            logger.debug(
                "axis request failed | ip=%s | path=%s | error=%s",
                self.ip,
                path,
                type(exc).__name__,
            )
            return None

    # ──────────────────────────────────────────────
    # Public API (factual only)
    # ──────────────────────────────────────────────

    async def get_serial(
        self,
        session: aiohttp.ClientSession,
    ) -> Optional[str]:
        logger.debug("axis get_serial | ip=%s", self.ip)

        data = await self._get_json(
            session,
            "/axis-cgi/basicdeviceinfo.cgi",
        )
        if not data:
            return None

        return data.get("SerialNumber") or data.get("serialNumber")

    async def get_model(
        self,
        session: aiohttp.ClientSession,
    ) -> Optional[str]:
        logger.debug("axis get_model | ip=%s", self.ip)

        data = await self._get_json(
            session,
            "/axis-cgi/basicdeviceinfo.cgi",
        )
        if not data:
            return None

        return (
            data.get("ProdNbr") or data.get("ProdFullName") or data.get("ProdShortName")
        )

    async def get_mac(
        self,
        session: aiohttp.ClientSession,
    ) -> Optional[str]:
        logger.debug("axis get_mac | ip=%s", self.ip)

        for path, params in (
            ("/axis-cgi/param.cgi", {"action": "list", "group": "Network"}),
            ("/axis-cgi/network/settings.cgi", None),
        ):
            data = await self._get_json(
                session,
                path,
                params=params,
            )
            if not data:
                continue

            mac = self._find_mac(data)
            if mac:
                return mac.upper().replace("-", ":")

        return None

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    @staticmethod
    def _find_mac(data: Any) -> Optional[str]:
        """
        Recursively search for MAC-like values in nested JSON.
        """
        if isinstance(data, dict):
            for key, value in data.items():
                if (
                    "mac" in key.lower()
                    and isinstance(value, str)
                    and len(value.replace(":", "").replace("-", "")) == 12
                ):
                    return value
                found = AxisVapixClient._find_mac(value)
                if found:
                    return found

        elif isinstance(data, list):
            for item in data:
                found = AxisVapixClient._find_mac(item)
                if found:
                    return found

        return None
