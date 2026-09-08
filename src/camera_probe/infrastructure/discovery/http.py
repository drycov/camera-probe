from __future__ import annotations

import asyncio
import logging
import re
from typing import Dict
from urllib.parse import urlparse

from camera_probe.infrastructure.http.client import HttpClient

logger = logging.getLogger(__name__)

VENDOR_HTTP_MARKERS: dict[str, list[str]] = {
    "hikvision": ["/ISAPI/System/deviceInfo", "/ISAPI/Security/userCheck"],
    "dahua": ["/cgi-bin/magicBox.cgi?action=getSystemInfo", "/cgi-bin/global.cgi?action=getCurrentTime"],
    "uniview": ["/cgi-bin/main-cgi?action=getDeviceInfo"],
    "xiongmai": ["/web/cgi-bin/hi3510/param.cgi"],
}

DEFAULT_PATHS = [
    "/",
    "/login",
    "/doc/page/login.asp",
    "/web/login",
    "/doc/index.html#/portal/login",
]

PREFERRED_HTTP_PORT_ORDER = (80, 443, 81, 8080, 8000, 8888)
MAX_CONCURRENT_HTTP_PROBES = 8


async def http_auth_fingerprint(
    ip: str,
    ports: list[int] | tuple[int, ...] = (80, 81, 8080, 8000, 8888),
    timeout: float = 2.0,
) -> Dict[str, object]:
    """Bounded HTTP fingerprinting.

    Port 443 is probed over HTTPS. Vendor probes run concurrently with a small
    semaphore instead of performing dozens of sequential timeout-bound requests.
    ``http_vendor_markers`` is always a list, matching the discovery engine API.
    """
    evidence: Dict[str, object] = {}
    ordered_ports = _sort_ports(ports)
    timeout = max(0.05, timeout)
    client = HttpClient(ip=ip, timeout=timeout, verify_ssl=False, prefer_https=False, try_anonymous=True)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_HTTP_PROBES)

    async def probe(url: str) -> tuple[str, dict | None]:
        async with semaphore:
            try:
                return url, await client.raw_get(url)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.debug("HTTP probe failed | url=%s | error=%s", url, type(exc).__name__)
                return url, None

    def make_url(port: int, path: str) -> str:
        scheme = "https" if port == 443 else "http"
        return f"{scheme}://{ip}:{port}{path}"

    # Strong vendor endpoints: all candidates are checked in one bounded wave.
    vendor_urls = [
        (vendor, make_url(port, path))
        for port in ordered_ports
        for vendor, paths in VENDOR_HTTP_MARKERS.items()
        for path in paths
    ]
    responses = await asyncio.gather(*(probe(url) for _, url in vendor_urls), return_exceptions=True)

    for meta, response in zip(vendor_urls, responses):
        vendor, url = meta
        if isinstance(response, BaseException):
            continue
        _, resp = response
        if not resp or resp.get("status") not in (200, 401, 403):
            continue

        headers = resp.get("headers") or {}
        markers = evidence.setdefault("http_vendor_markers", [])
        if vendor not in markers:
            markers.append(vendor)
        evidence.setdefault("url_tried", url)
        evidence.setdefault("status", str(resp["status"]))

        www_auth = headers.get("www-authenticate")
        if www_auth:
            evidence["www_authenticate"] = www_auth
            realm = _extract_realm(www_auth)
            if realm:
                evidence["realm"] = realm
        # A strong marker is sufficient; no need to perform generic login probes.
        return evidence

    # Weak generic probing is also bounded. Stop on an authentication response,
    # but retain Server/X-* evidence when the page itself is accessible.
    generic_urls = [make_url(port, path) for port in ordered_ports for path in DEFAULT_PATHS]
    responses = await asyncio.gather(*(probe(url) for url in generic_urls), return_exceptions=True)

    for url, response in zip(generic_urls, responses):
        if isinstance(response, BaseException):
            continue
        _, resp = response
        if not resp:
            continue

        status = resp.get("status")
        headers = resp.get("headers") or {}
        evidence.setdefault("status", str(status))
        evidence.setdefault("url_tried", url)

        www_auth = headers.get("www-authenticate")
        if www_auth:
            evidence["www_authenticate"] = www_auth
            auth_type = _extract_auth_type(www_auth)
            if auth_type:
                evidence["auth_type"] = auth_type
            realm = _extract_realm(www_auth)
            if realm:
                evidence["realm"] = realm
            return evidence

        server = headers.get("server")
        if server:
            evidence.setdefault("http_server", server)

        for key, value in headers.items():
            if key.startswith("x-"):
                evidence.setdefault(f"header_{key}", value)

        if status in (401, 403):
            return evidence

    if not evidence:
        evidence["status"] = "no_response"
    return evidence


def _extract_realm(www_auth: str) -> str | None:
    m = re.search(r'realm="([^"]+)"', www_auth, re.IGNORECASE)
    return m.group(1) if m else None


def _extract_auth_type(www_auth: str) -> str | None:
    m = re.match(r"^(Basic|Digest)\s", www_auth, re.IGNORECASE)
    return m.group(1).capitalize() if m else None


def _sort_ports(ports: list[int] | tuple[int, ...]) -> list[int]:
    preferred_index = {port: index for index, port in enumerate(PREFERRED_HTTP_PORT_ORDER)}
    return sorted(ports, key=lambda port: (preferred_index.get(port, len(PREFERRED_HTTP_PORT_ORDER)), port))
