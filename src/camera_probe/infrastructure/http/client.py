from __future__ import annotations

import asyncio
import logging
from typing import Optional, Iterable
from urllib.parse import urljoin

import aiohttp
import httpx
import requests
from requests.auth import HTTPDigestAuth, HTTPBasicAuth

logger = logging.getLogger(__name__)


class HttpClient:
    """
    Universal HTTP client for embedded devices.

    Contract:
    - Digest → Basic → Anonymous
    - requests.Session for real Digest (Hikvision-compatible)
    - async wrapper via asyncio.to_thread
    - HTTP / HTTPS base discovery
    """

    def __init__(
        self,
        *,
        ip: str,
        timeout: float = 5.0,
        verify_ssl: bool = False,
        prefer_https: bool = False,
        try_anonymous: bool = True,
    ) -> None:
        self.ip = ip
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.prefer_https = prefer_https
        self.try_anonymous = try_anonymous

        self._base_url: Optional[str] = None

        self._digest: Optional[HTTPDigestAuth] = None
        self._basic: Optional[HTTPBasicAuth] = None
        self._session: Optional[requests.Session] = None

    # ────────────────────────────────────────────────
    # Auth
    # ────────────────────────────────────────────────

    def set_auth(self, username: str | None, password: str | None) -> None:
        if not username or not password:
            return

        self._digest = HTTPDigestAuth(username, password)
        self._basic = HTTPBasicAuth(username, password)

        session = requests.Session()
        session.auth = self._digest
        self._session = session

    def close(self) -> None:
        if self._session:
            self._session.close()
            self._session = None

    # ────────────────────────────────────────────────
    # Base URL discovery (aiohttp, HEAD)
    # ────────────────────────────────────────────────

    async def get_base_url(
        self,
        test_paths: Iterable[str],
        ok_statuses: tuple[int, ...] = (200, 401, 403),
    ) -> Optional[str]:
        if self._base_url:
            return self._base_url

        schemes = ["https", "http"] if self.prefer_https else ["http", "https"]

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        ) as session:
            for scheme in schemes:
                base = f"{scheme}://{self.ip}"
                for path in test_paths:
                    url = urljoin(base, path)
                    try:
                        async with session.head(
                            url,
                            allow_redirects=False,
                            ssl=self.verify_ssl,
                        ) as resp:
                            if resp.status in ok_statuses:
                                self._base_url = base
                                logger.debug("Base URL detected: %s", base)
                                return base
                    except Exception:
                        continue

        return None

    # ────────────────────────────────────────────────
    # Sync HTTP core (requests)
    # ────────────────────────────────────────────────

    def _request_sync(
        self,
        base: str,
        path: str,
        *,
        allow_anonymous: bool = False,
        force_basic: bool = False,
    ) -> Optional[str]:
        url = urljoin(base, path)
        r: Optional[requests.Response] = None

        try:
            # 0) Anonymous
            if allow_anonymous and self.try_anonymous:
                r = requests.get(
                    url,
                    timeout=self.timeout,
                    verify=self.verify_ssl,
                )
                if r.status_code == 200:
                    return r.text

            # 1) DIGEST — CORRECT
            if self._digest:
                self._session.auth = self._digest

                r = self._session.get(
                    url,
                    timeout=self.timeout,
                    verify=self.verify_ssl,
                )

                if r.status_code == 200:
                    logger.debug("HTTP OK (digest) | %s", path)
                    return r.text

            # 2) BASIC fallback
            if self._basic and (force_basic or (r and r.status_code == 401)):
                r = requests.get(
                    url,
                    auth=self._basic,
                    timeout=self.timeout,
                    verify=self.verify_ssl,
                )
                if r.status_code == 200:
                    return r.text

            logger.debug(
                "HTTP non-200 | ip=%s | path=%s | status=%s",
                self.ip,
                path,
                getattr(r, "status_code", None),
            )
            return None

        except Exception as exc:
            logger.debug(
                "HTTP failed | ip=%s | path=%s | error=%s",
                self.ip,
                path,
                type(exc).__name__,
            )
            return None


    # ────────────────────────────────────────────────
    # Async wrapper
    # ────────────────────────────────────────────────

    async def get(
        self,
        path: str,
        *,
        allow_anonymous: bool = False,
        force_basic: bool = False,
        base_url: Optional[str] = None,
    ) -> Optional[str]:
        base = base_url or self._base_url
        if not base:
            return None

        return await asyncio.to_thread(
            self._request_sync,
            base,
            path,
            allow_anonymous=allow_anonymous,
            force_basic=force_basic,
        )

    # ────────────────────────────────────────────────
    # LOW-LEVEL RAW GET (discovery)
    # ────────────────────────────────────────────────

    async def raw_get(self, url: str) -> Optional[dict]:
        """
        Low-level HTTP GET.
        - NEVER raises on HTTP status
        - returns status + headers
        - used by discovery
        """
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                verify=self.verify_ssl,
                follow_redirects=False,
                headers={"User-Agent": "camera-probe/1.0"},
            ) as client:
                r = await client.get(url)
                return {
                    "status": r.status_code,
                    "headers": {k.lower(): v for k, v in r.headers.items()},
                }
        except httpx.RequestError as exc:
            logger.trace(
                "raw_get failed | url=%s | error=%s",
                url,
                type(exc).__name__,
            )
            return None
