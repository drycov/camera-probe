from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import urljoin

import requests
from requests.auth import HTTPDigestAuth, HTTPBasicAuth

logger = logging.getLogger(__name__)


class HikvisionHttpClient:
    """
    Hikvision-safe HTTP client.

    GUARANTEES:
    - Correct Digest handshake (browser-like)
    - Works with ISAPI
    - No async, no aiohttp, no httpx
    """

    def __init__(
        self,
        *,
        ip: str,
        username: str,
        password: str,
        timeout: float = 5.0,
        verify_ssl: bool = False,
        scheme: str = "http",
    ) -> None:
        self.base_url = f"{scheme}://{ip}"
        self.timeout = timeout
        self.verify_ssl = verify_ssl

        self._digest = HTTPDigestAuth(username, password)
        self._basic = HTTPBasicAuth(username, password)

        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "camera-probe/1.0",
            "Connection": "close",
            "Accept": "*/*",
        })

    # ────────────────────────────────────────────────
    # CORE REQUEST
    # ────────────────────────────────────────────────

    def get(
        self,
        path: str,
        *,
        allow_basic_fallback: bool = True,
    ) -> Optional[str]:
        url = urljoin(self.base_url, path)

        try:
            # 1️⃣ CHALLENGE (NO AUTH)
            r = self._session.get(
                url,
                timeout=self.timeout,
                verify=self.verify_ssl,
            )

            if r.status_code != 401:
                logger.debug("Unexpected status on challenge: %s", r.status_code)

            # 2️⃣ DIGEST AUTH (SAME SESSION)
            self._session.auth = self._digest
            r = self._session.get(
                url,
                timeout=self.timeout,
                verify=self.verify_ssl,
            )

            if r.status_code == 200:
                logger.debug("HTTP OK (digest) | %s", path)
                return r.text

            # 3️⃣ BASIC FALLBACK (rare but exists)
            if allow_basic_fallback:
                r = requests.get(
                    url,
                    auth=self._basic,
                    timeout=self.timeout,
                    verify=self.verify_ssl,
                    headers={"Connection": "close"},
                )
                if r.status_code == 200:
                    logger.debug("HTTP OK (basic) | %s", path)
                    return r.text

            logger.debug(
                "HTTP failed | path=%s | status=%s",
                path,
                r.status_code,
            )
            return None

        except Exception as exc:
            logger.debug(
                "HTTP exception | path=%s | error=%s",
                path,
                type(exc).__name__,
            )
            return None

    # ────────────────────────────────────────────────
    # LIFECYCLE
    # ────────────────────────────────────────────────

    def close(self) -> None:
        try:
            self._session.close()
        except Exception:
            pass
