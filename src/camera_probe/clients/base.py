from __future__ import annotations

import time
import logging
from typing import Optional, Iterable, ClassVar
from urllib.parse import urljoin

import aiohttp

from camera_probe.utils.net_async import tcp_check

logger = logging.getLogger(__name__)


class BaseClient:
    """
    Base async client for camera HTTP APIs.

    Responsibilities:
    - determine working base URL (http / https)
    - cache base URL with TTL
    - perform TCP pre-check to avoid slow timeouts
    - provide deterministic, low-noise logging

    Contract:
    - subclasses MUST define class attribute: vendor: str
    """

    vendor: ClassVar[str]  # required for ClientRegistry

    BASE_TTL_SECONDS: int = 300  # safe for cameras

    def __init__(
        self,
        ip: str,
        *,
        timeout: float,
        prefer_https: bool = False,
        verify_ssl: bool = False,
    ) -> None:
        if not ip:
            raise ValueError("IP address is required")

        if timeout <= 0:
            raise ValueError("Timeout must be positive")

        self.ip = ip.strip()
        self.timeout = timeout
        self.prefer_https = prefer_https
        self.verify_ssl = verify_ssl

        self._base_url: Optional[str] = None
        self._base_url_ts: float = 0.0

        if not getattr(self, "vendor", None):
            raise TypeError(
                f"{self.__class__.__name__} must define class attribute `vendor: str`"
            )

    # ──────────────────────────────────────────────
    # TTL helpers
    # ──────────────────────────────────────────────

    def _base_valid(self) -> bool:
        return (
            self._base_url is not None
            and (time.monotonic() - self._base_url_ts) < self.BASE_TTL_SECONDS
        )

    def _set_base(self, base: str) -> None:
        self._base_url = base
        self._base_url_ts = time.monotonic()

    # ──────────────────────────────────────────────
    # Base URL discovery
    # ──────────────────────────────────────────────

    async def discover_base_url(
        self,
        session: aiohttp.ClientSession,
        *,
        test_paths: Iterable[str],
        ok_statuses: Iterable[int] = (200, 401),
        tcp_timeout: float = 1.8,
        request_timeout: float = 3.0,
    ) -> Optional[str]:
        """
        Determine working base URL (http or https).

        Strategy:
        1. Use cached value if valid
        2. TCP pre-check (80 / 443)
        3. Iterate over known test paths
        3.1 HEAD request
        3.2 GET fallback (critical for some vendors, e.g. Dahua)
        """

        # ─── cache ────────────────────────────
        if self._base_valid():
            logger.debug(
                "base_url cache hit | vendor=%s | ip=%s | base=%s",
                self.vendor,
                self.ip,
                self._base_url,
            )
            return self._base_url

        candidates = (
            [f"https://{self.ip}", f"http://{self.ip}"]
            if self.prefer_https
            else [f"http://{self.ip}", f"https://{self.ip}"]
        )

        logger.debug(
            "base_url discovery start | vendor=%s | ip=%s | candidates=%s | paths=%s",
            self.vendor,
            self.ip,
            candidates,
            list(test_paths),
        )

        for base in candidates:
            proto = "https" if base.startswith("https") else "http"
            port = 443 if proto == "https" else 80

            # ─── TCP pre-check ─────────────────
            if not await tcp_check(self.ip, port, timeout=tcp_timeout):
                logger.debug(
                    "base_url tcp closed | vendor=%s | ip=%s | port=%d",
                    self.vendor,
                    self.ip,
                    port,
                )
                continue

            # ─── iterate test paths ────────────
            for path in test_paths:
                url = urljoin(base, path)

                # ─── HEAD attempt ───────────────
                try:
                    async with session.head(
                        url,
                        timeout=aiohttp.ClientTimeout(total=request_timeout),
                        ssl=self.verify_ssl,
                    ) as resp:
                        logger.debug(
                            "base_url HEAD | vendor=%s | ip=%s | url=%s | status=%d",
                            self.vendor,
                            self.ip,
                            url,
                            resp.status,
                        )

                        if resp.status in ok_statuses:
                            self._set_base(base)
                            logger.debug(
                                "base_url determined (HEAD) | vendor=%s | ip=%s | base=%s | path=%s",
                                self.vendor,
                                self.ip,
                                base,
                                path,
                            )
                            return base

                except Exception as exc:
                    logger.debug(
                        "base_url HEAD failed | vendor=%s | ip=%s | url=%s | error=%s",
                        self.vendor,
                        self.ip,
                        url,
                        type(exc).__name__,
                    )

                # ─── GET fallback ───────────────
                try:
                    async with session.get(
                        url,
                        timeout=aiohttp.ClientTimeout(total=request_timeout),
                        ssl=self.verify_ssl,
                    ) as resp:
                        logger.debug(
                            "base_url GET | vendor=%s | ip=%s | url=%s | status=%d",
                            self.vendor,
                            self.ip,
                            url,
                            resp.status,
                        )

                        if resp.status in ok_statuses:
                            self._set_base(base)
                            logger.debug(
                                "base_url determined (GET) | vendor=%s | ip=%s | base=%s | path=%s",
                                self.vendor,
                                self.ip,
                                base,
                                path,
                            )
                            return base

                except Exception as exc:
                    logger.debug(
                        "base_url GET failed | vendor=%s | ip=%s | url=%s | error=%s",
                        self.vendor,
                        self.ip,
                        url,
                        type(exc).__name__,
                    )

        logger.warning(
            "base_url not found | vendor=%s | ip=%s | tried=%s",
            self.vendor,
            self.ip,
            candidates,
        )
        return None
