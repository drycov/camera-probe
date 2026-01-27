from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional, Iterable
from urllib.parse import urljoin

import aiohttp
import requests
from requests.auth import HTTPDigestAuth, HTTPBasicAuth

logger = logging.getLogger(__name__)


class HttpClient:
    """
    Universal HTTP client for embedded devices (Hikvision / Dahua / OEM).

    Principles:
    - requests.Session + DigestAuth is the source of truth
    - aiohttp ONLY for base URL discovery
    - async via asyncio.to_thread
    - never raises on HTTP errors
    """

    BASE_TTL = 300  # seconds

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
        self._base_ts: float = 0.0

        self._digest: Optional[HTTPDigestAuth] = None
        self._basic: Optional[HTTPBasicAuth] = None

        self._session: Optional[requests.Session] = None

    # ─────────────────────────────────────────────
    # Auth
    # ─────────────────────────────────────────────

    def set_auth(self, username: str | None, password: str | None) -> None:
        if not username or not password:
            return

        self._digest = HTTPDigestAuth(username, password)
        self._basic = HTTPBasicAuth(username, password)

        session = requests.Session()
        session.auth = self._digest
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept": "application/xml",
                "Connection": "close",
            }
        )

        self._session = session

    def close(self) -> None:
        if self._session:
            self._session.close()
            self._session = None

    # ─────────────────────────────────────────────
    # Base URL discovery (aiohttp)
    # ─────────────────────────────────────────────

    async def get_base_url(
        self,
        test_paths: Iterable[str],
        ok_statuses: tuple[int, ...] = (200, 401, 403),
    ) -> Optional[str]:
        if self._base_url and (time.monotonic() - self._base_ts) < self.BASE_TTL:
            return self._base_url

        schemes = ["https", "http"] if self.prefer_https else ["http", "https"]

        timeout = aiohttp.ClientTimeout(total=self.timeout)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for scheme in schemes:
                base = f"{scheme}://{self.ip}"

                for path in test_paths:
                    url = urljoin(base, path)

                    # HEAD
                    try:
                        async with session.head(
                            url,
                            ssl=self.verify_ssl,
                            allow_redirects=False,
                        ) as resp:
                            if resp.status in ok_statuses:
                                self._base_url = base
                                self._base_ts = time.monotonic()
                                logger.debug("Base URL detected (HEAD): %s", base)
                                return base
                    except Exception:
                        pass

                    # GET fallback (CRITICAL for Hikvision)
                    try:
                        async with session.get(
                            url,
                            ssl=self.verify_ssl,
                            allow_redirects=False,
                        ) as resp:
                            if resp.status in ok_statuses:
                                self._base_url = base
                                self._base_ts = time.monotonic()
                                logger.debug("Base URL detected (GET): %s", base)
                                return base
                    except Exception:
                        pass

        logger.warning("Base URL not found | ip=%s", self.ip)
        return None

    # ─────────────────────────────────────────────
    # Sync HTTP core (requests)
    # ─────────────────────────────────────────────

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
            # 0) Anonymous
            if allow_anonymous and self.try_anonymous:
                r = requests.get(
                    url,
                    timeout=self.timeout,
                    verify=self.verify_ssl,
                )
                if r.status_code == 200:
                    return r.text

            # 1) Digest (primary)
            if self._session and self._digest:
                r = self._session.get(
                    url,
                    timeout=self.timeout,
                    verify=self.verify_ssl,
                )
                if r.status_code == 200:
                    return r.text

            # 2) Basic fallback
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

    # ─────────────────────────────────────────────
    # Async wrapper
    # ─────────────────────────────────────────────

    async def get(
        self,
        path: str,
        *,
        base_url: Optional[str] = None,
        allow_anonymous: bool = False,
        force_basic: bool = False,
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
