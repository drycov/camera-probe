from __future__ import annotations

import logging
import re
from typing import Dict, List

from camera_probe.infrastructure.http.client import HttpClient

logger = logging.getLogger(__name__)


VENDOR_HTTP_MARKERS: dict[str, list[str]] = {
    "hikvision": [
        "/ISAPI/System/deviceInfo",
        "/ISAPI/Security/userCheck",
    ],
    "dahua": [
        "/cgi-bin/magicBox.cgi?action=getSystemInfo",
        "/cgi-bin/global.cgi?action=getCurrentTime",
    ],
    "uniview": [
        "/cgi-bin/main-cgi?action=getDeviceInfo",
    ],
    "xiongmai": [
        "/web/cgi-bin/hi3510/param.cgi",
    ],
}

DEFAULT_PATHS = [
    "/",
    "/login",
    "/doc/page/login.asp",
    "/web/login",
    "/doc/index.html#/portal/login",
]


async def http_auth_fingerprint(
    ip: str,
    ports: list[int] = (80, 81, 8080, 8000, 8888),
    timeout: float = 2.0,
) -> Dict[str, str]:
    """
    HTTP discovery via vendor API markers.

    Priority:
      1. Vendor-specific API endpoints (STRONG)
      2. WWW-Authenticate
      3. Server / X-* headers
    """

    evidence: Dict[str, str] = {}

    logger.debug(
        "HTTP discovery started | ip=%s | ports=%s | timeout=%.1fs",
        ip,
        ports,
        timeout,
    )

    client = HttpClient(
        ip=ip,
        timeout=timeout,
        verify_ssl=False,
        prefer_https=False,
        try_anonymous=True,
    )

    # ────────────────────────────────────────────────
    # 1. Vendor-specific API markers (STRONG)
    # ────────────────────────────────────────────────
    for port in ports:
        for vendor, paths in VENDOR_HTTP_MARKERS.items():
            for path in paths:
                url = f"http://{ip}:{port}{path}"
                logger.trace("HTTP vendor probe: %s", url)

                try:
                    resp = await client.raw_get(url)

                    if not resp:
                        continue

                    status = resp["status"]
                    headers = resp["headers"]

                    if status in (200, 401, 403):
                        logger.debug(
                            "HTTP vendor marker detected | vendor=%s | url=%s | status=%s",
                            vendor,
                            url,
                            status,
                        )

                        evidence["http_vendor_markers"] = [vendor]
                        evidence["url_tried"] = url
                        evidence["status"] = str(status)

                        www_auth = headers.get("www-authenticate")
                        if www_auth:
                            evidence["www_authenticate"] = www_auth

                            realm = _extract_realm(www_auth)
                            if realm:
                                evidence["realm"] = realm

                        return evidence  # 🔴 STRONG signal → exit

                except Exception as exc:
                    logger.trace(
                        "HTTP vendor probe failed | url=%s | error=%s",
                        url,
                        type(exc).__name__,
                    )

    # ────────────────────────────────────────────────
    # 2. Generic HTTP probing (fallback)
    # ────────────────────────────────────────────────
    for port in ports:
        for path in DEFAULT_PATHS:
            url = f"http://{ip}:{port}{path}"
            logger.trace("HTTP probe: %s", url)

            try:
                resp = await client.raw_get(url)

                if not resp:
                    continue

                status = resp["status"]
                headers = resp["headers"]

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

                for k, v in headers.items():
                    if k.startswith("x-"):
                        evidence.setdefault(f"header_{k}", v)

                if status in (401, 403):
                    return evidence

            except Exception as exc:
                evidence.setdefault(
                    "error",
                    f"{type(exc).__name__}: {exc}",
                )

    if not evidence:
        evidence["status"] = "no_response"

    return evidence

def _extract_realm(www_auth: str) -> str | None:
    m = re.search(r'realm="([^"]+)"', www_auth, re.IGNORECASE)
    return m.group(1) if m else None


def _extract_auth_type(www_auth: str) -> str | None:
    m = re.match(r"^(Basic|Digest)\s", www_auth, re.IGNORECASE)
    return m.group(1).capitalize() if m else None