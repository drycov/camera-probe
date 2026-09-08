from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, Iterable, Optional
from urllib.parse import urljoin

import aiohttp
import requests
from requests.auth import HTTPDigestAuth, HTTPBasicAuth

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/xml",
    "Connection": "close",
}


class HttpClient:
    """HTTP client for embedded devices with race-safe connection state."""

    BASE_TTL = 300
    BASE_NOT_FOUND_TTL = 300

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
        self.timeout = max(0.05, timeout)
        self.verify_ssl = verify_ssl
        self.prefer_https = prefer_https
        self.try_anonymous = try_anonymous

        self._base_url: Optional[str] = None
        self._base_ts = 0.0
        self._base_not_found_ts = 0.0
        self._base_lock = asyncio.Lock()

        self._digest: Optional[HTTPDigestAuth] = None
        self._basic: Optional[HTTPBasicAuth] = None
        self._session: Optional[requests.Session] = None
        self._session_lock = threading.RLock()

    def set_auth(self, username: str | None, password: str | None) -> None:
        if not username or not password:
            return

        with self._session_lock:
            self._digest = HTTPDigestAuth(username, password)
            self._basic = HTTPBasicAuth(username, password)
            if self._session:
                self._session.close()
            session = requests.Session()
            session.auth = self._digest
            session.headers.update(DEFAULT_HEADERS)
            self._session = session

    def close(self) -> None:
        with self._session_lock:
            if self._session:
                self._session.close()
                self._session = None

    async def get_base_url(
        self,
        test_paths: Iterable[str],
        ok_statuses: tuple[int, ...] = (200, 401, 403),
    ) -> Optional[str]:
        now = time.monotonic()
        if self._base_url and now - self._base_ts < self.BASE_TTL:
            return self._base_url
        if now - self._base_not_found_ts < self.BASE_NOT_FOUND_TTL:
            return None

        # Several adapter coroutines may ask for the base URL simultaneously.
        # Only one discovery sequence is allowed to mutate the cache.
        async with self._base_lock:
            now = time.monotonic()
            if self._base_url and now - self._base_ts < self.BASE_TTL:
                return self._base_url
            if now - self._base_not_found_ts < self.BASE_NOT_FOUND_TTL:
                return None

            schemes = ["https", "http"] if self.prefer_https else ["http", "https"]
            timeout = aiohttp.ClientTimeout(total=self.timeout)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                for scheme in schemes:
                    base = f"{scheme}://{self.ip}"
                    for path in test_paths:
                        detected = await self._probe_base_url(
                            session=session,
                            base=base,
                            url=urljoin(base, path),
                            ok_statuses=ok_statuses,
                        )
                        if detected:
                            return detected

            self._base_not_found_ts = time.monotonic()
            logger.debug("Base URL not found | ip=%s", self.ip)
            return None

    async def _probe_base_url(
        self,
        *,
        session: aiohttp.ClientSession,
        base: str,
        url: str,
        ok_statuses: tuple[int, ...],
    ) -> Optional[str]:
        for method in ("head", "get"):
            try:
                request = getattr(session, method)
                async with request(url, ssl=self.verify_ssl, allow_redirects=False) as resp:
                    if resp.status in ok_statuses:
                        self._base_url = base
                        self._base_ts = time.monotonic()
                        logger.debug("Base URL detected (%s): %s", method.upper(), base)
                        return base
            except asyncio.CancelledError:
                raise
            except Exception:
                continue
        return None

    def _request_sync(
        self,
        base: str,
        path: str,
        *,
        allow_anonymous: bool = False,
        force_basic: bool = False,
    ) -> Optional[str]:
        url = urljoin(base, path)
        response: requests.Response | None = None

        try:
            if allow_anonymous and self.try_anonymous:
                response = requests.get(
                    url, timeout=self.timeout, verify=self.verify_ssl, headers=DEFAULT_HEADERS
                )
                if response.status_code == 200:
                    return response.text

            with self._session_lock:
                session = self._session
                digest = self._digest
                basic = self._basic
                if session and digest:
                    response = session.get(url, timeout=self.timeout, verify=self.verify_ssl)
                    if response.status_code == 200:
                        return response.text

                should_try_basic = basic and (
                    force_basic or (response is not None and response.status_code == 401)
                )

            if should_try_basic:
                response = requests.get(
                    url,
                    auth=basic,
                    timeout=self.timeout,
                    verify=self.verify_ssl,
                    headers=DEFAULT_HEADERS,
                )
                if response.status_code == 200:
                    return response.text

            logger.debug(
                "HTTP non-200 | ip=%s | path=%s | status=%s",
                self.ip,
                path,
                getattr(response, "status_code", None),
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

    def _raw_get_sync(self, url: str) -> Optional[dict[str, Any]]:
        try:
            response = requests.get(
                url,
                timeout=self.timeout,
                verify=self.verify_ssl,
                allow_redirects=False,
                headers=DEFAULT_HEADERS,
            )
            return {
                "status": response.status_code,
                "headers": {key.lower(): value for key, value in response.headers.items()},
                "text": response.text,
            }
        except Exception as exc:
            logger.debug(
                "HTTP raw_get failed | ip=%s | url=%s | error=%s",
                self.ip,
                url,
                type(exc).__name__,
            )
            return None

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

    async def raw_get(self, url: str) -> Optional[dict[str, Any]]:
        return await asyncio.to_thread(self._raw_get_sync, url)
