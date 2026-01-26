from __future__ import annotations
import asyncio

import aiohttp
import logging
from typing import Dict, Iterable

logger = logging.getLogger(__name__)


SOAP_BODY = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
  <s:Body>
    <tds:GetDeviceInformation/>
  </s:Body>
</s:Envelope>
"""


async def onvif_get_device_information(
    xaddr: str,
    timeout: float = 3.0,
) -> Dict[str, str]:
    """
    Call ONVIF GetDeviceInformation on device_service XAddr.

    Returns evidence dict or empty dict if not доступно.
    """

    logger.debug("ONVIF GetDeviceInformation started: %s", xaddr)

    headers = {
        "Content-Type": "application/soap+xml; charset=utf-8",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                xaddr,
                data=SOAP_BODY,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:

                logger.trace(
                    "ONVIF GetDeviceInformation HTTP %s",
                    resp.status,
                )

                if resp.status == 401:
                    logger.debug(
                        "ONVIF GetDeviceInformation requires authentication: %s",
                        xaddr,
                    )
                    return {}

                if resp.status != 200:
                    logger.debug(
                        "ONVIF GetDeviceInformation unexpected status %s on %s",
                        resp.status,
                        xaddr,
                    )
                    return {}

                text = await resp.text(errors="ignore")
                logger.trace(
                    "ONVIF GetDeviceInformation response: %s",
                    text,
                )

    except aiohttp.ClientError as e:
        logger.debug(
            "ONVIF GetDeviceInformation HTTP error on %s: %s",
            xaddr,
            e,
        )
        return {}

    except Exception:
        logger.exception(
            "ONVIF GetDeviceInformation unexpected error on %s",
            xaddr,
        )
        return {}

    # ─── Parse XML (simple, dependency-free) ─────────────────────

    def _extract(tag: str) -> str | None:
        start = text.find(f"<{tag}>")
        if start == -1:
            return None
        start += len(tag) + 2
        end = text.find(f"</{tag}>", start)
        if end == -1:
            return None
        return text[start:end].strip()

    evidence: Dict[str, str] = {}

    for field in (
        "Manufacturer",
        "Model",
        "FirmwareVersion",
        "SerialNumber",
        "HardwareId",
    ):
        value = _extract(field)
        if value:
            evidence[field.lower()] = value

    if evidence:
        logger.debug(
            "ONVIF device information collected: %s",
            evidence,
        )

    return evidence

async def onvif_unicast_probe(
    ip: str,
    ports: list[int],
) -> list[str]:
    """
    Try common ONVIF XAddr endpoints via unicast.
    """
    xaddrs: list[str] = []

    for port in ports:
        url = f"http://{ip}:{port}/onvif/device_service"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    data=SOAP_BODY,
                    headers={"Content-Type": "application/soap+xml"},
                    timeout=aiohttp.ClientTimeout(total=2.0),
                ) as resp:
                    if resp.status in (200, 401):
                        logger.debug(
                            "ONVIF unicast endpoint detected: %s (status=%s)",
                            url,
                            resp.status,
                        )
                        xaddrs.append(url)
        except Exception:
            logger.trace("ONVIF unicast failed: %s", url)

    return xaddrs

async def onvif_https_unicast_probe(
    ip: str,
    ports: Iterable[int],
    timeout: float = 3.0,
) -> list[str]:
    """
    Try HTTPS ONVIF device_service endpoints.

    Returns list of working XAddr URLs.
    """

    xaddrs: list[str] = []

    for port in ports:
        url = f"https://{ip}:{port}/onvif/device_service"
        logger.trace("ONVIF HTTPS probe: %s", url)

        try:
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False)  # камеры часто с self-signed
            ) as session:
                async with session.post(
                    url,
                    data=SOAP_BODY,
                    headers={
                        "Content-Type": "application/soap+xml; charset=utf-8",
                    },
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:

                    logger.trace(
                        "ONVIF HTTPS response: %s status=%s",
                        url,
                        resp.status,
                    )

                    # 200 — отлично
                    # 401 — ONVIF есть, но требует auth
                    if resp.status in (200, 401):
                        logger.debug(
                            "ONVIF HTTPS endpoint detected: %s (status=%s)",
                            url,
                            resp.status,
                        )
                        xaddrs.append(url)

        except aiohttp.ClientConnectorError:
            logger.trace("ONVIF HTTPS connect failed: %s", url)
        except asyncio.TimeoutError:
            logger.trace("ONVIF HTTPS timeout: %s", url)
        except Exception:
            logger.exception("ONVIF HTTPS unexpected error: %s", url)

    return xaddrs

async def onvif_https_auth_probe(
    *,
    ip: str,
    ports: Iterable[int],
    username: str,
    password: str,
    timeout: float = 3.0,
) -> list[str]:
    """
    Try HTTPS ONVIF device_service with Basic authentication.

    Digest is intentionally NOT used:
    - aiohttp does not support it
    - HTTPS + Basic works for most cameras
    """

    xaddrs: list[str] = []

    auth = aiohttp.BasicAuth(username, password)

    for port in ports:
        url = f"https://{ip}:{port}/onvif/device_service"
        logger.trace("ONVIF HTTPS Basic auth probe: %s", url)

        try:
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False),
                auth=auth,
            ) as session:
                async with session.post(
                    url,
                    data=SOAP_BODY,
                    headers={
                        "Content-Type": "application/soap+xml; charset=utf-8",
                    },
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:

                    logger.trace(
                        "ONVIF HTTPS Basic auth response: %s status=%s",
                        url,
                        resp.status,
                    )

                    if resp.status == 200:
                        logger.debug(
                            "ONVIF HTTPS Basic auth success: %s",
                            url,
                        )
                        xaddrs.append(url)
                        return xaddrs

                    if resp.status == 401:
                        logger.debug(
                            "ONVIF HTTPS Basic auth rejected (401): %s",
                            url,
                        )

        except asyncio.TimeoutError:
            logger.trace("ONVIF HTTPS Basic auth timeout: %s", url)
        except aiohttp.ClientError as e:
            logger.trace(
                "ONVIF HTTPS Basic auth error: %s %s",
                url,
                e,
            )
        except Exception:
            logger.exception(
                "ONVIF HTTPS Basic auth unexpected error: %s",
                url,
            )

    return xaddrs

