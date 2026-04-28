from __future__ import annotations
import asyncio
import base64
import hashlib
import os
import xml.etree.ElementTree as ET

import aiohttp
import logging
from datetime import datetime, timezone
from typing import Dict, Iterable
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


SOAP_BODY_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl"
            xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
            xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
  {header}
  <s:Body>
    <tds:GetDeviceInformation/>
  </s:Body>
</s:Envelope>
"""


async def onvif_get_device_information(
    xaddr: str,
    timeout: float = 3.0,
    username: str | None = None,
    password: str | None = None,
) -> Dict[str, str]:
    """
    Call ONVIF GetDeviceInformation on device_service XAddr.

    Returns evidence dict or empty dict if not доступно.
    """

    logger.debug("ONVIF GetDeviceInformation started: %s", xaddr)

    request_variants = [_build_get_device_information_body()]
    if username and password:
        request_variants.append(
            _build_get_device_information_body(
                username=username,
                password=password,
            )
        )

    last_text = ""
    for index, body in enumerate(request_variants, start=1):
        response = await _post_soap(
            xaddr=xaddr,
            body=body,
            timeout=timeout,
        )
        if response is None:
            continue

        status, text = response
        last_text = text

        logger.trace(
            "ONVIF GetDeviceInformation HTTP %s attempt=%s",
            status,
            index,
        )

        if status == 401:
            logger.debug(
                "ONVIF GetDeviceInformation requires authentication: %s attempt=%s",
                xaddr,
                index,
            )
            continue

        if status != 200:
            logger.debug(
                "ONVIF GetDeviceInformation unexpected status %s on %s attempt=%s",
                status,
                xaddr,
                index,
            )
            continue

        logger.trace(
            "ONVIF GetDeviceInformation response: %s",
            text,
        )

        evidence = _parse_device_information_xml(text)
        if evidence:
            logger.debug(
                "ONVIF device information collected: %s",
                evidence,
            )
            if index > 1:
                evidence["onvif_auth"] = "wsse_username_token"
            return evidence

        if _is_not_authorized_fault(text):
            logger.debug(
                "ONVIF GetDeviceInformation returned authorization fault: %s attempt=%s",
                xaddr,
                index,
            )
            continue

    if last_text and _is_not_authorized_fault(last_text):
        logger.debug("ONVIF GetDeviceInformation authorization failed on %s", xaddr)

    return {}

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
                    data=_build_get_device_information_body(),
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
                    data=_build_get_device_information_body(),
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
                    data=_build_get_device_information_body(),
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


def _parse_device_information_xml(text: str) -> Dict[str, str]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        logger.debug("ONVIF device information XML parse failed")
        return {}

    evidence: Dict[str, str] = {}

    field_map = {
        "Manufacturer": "onvif_manufacturer",
        "Model": "onvif_model",
        "FirmwareVersion": "onvif_firmwareversion",
        "SerialNumber": "onvif_serialnumber",
        "HardwareId": "onvif_hardwareid",
    }

    for tag, key in field_map.items():
        value = _find_text(root, tag)
        if value:
            evidence[key] = value

    return evidence


def _find_text(root: ET.Element, tag_suffix: str) -> str | None:
    for element in root.iter():
        if element.tag.endswith(tag_suffix) and element.text:
            return element.text.strip()
    return None


def _build_get_device_information_body(
    *,
    username: str | None = None,
    password: str | None = None,
) -> str:
    header = ""
    if username and password:
        created = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        nonce_bytes = os.urandom(16)
        digest = hashlib.sha1(
            nonce_bytes + created.encode("utf-8") + password.encode("utf-8")
        ).digest()
        password_digest = base64.b64encode(digest).decode("ascii")
        nonce = base64.b64encode(nonce_bytes).decode("ascii")

        header = f"""
  <s:Header>
    <wsse:Security s:mustUnderstand="1">
      <wsse:UsernameToken>
        <wsse:Username>{_xml_escape(username)}</wsse:Username>
        <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest">{password_digest}</wsse:Password>
        <wsse:Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">{nonce}</wsse:Nonce>
        <wsu:Created>{created}</wsu:Created>
      </wsse:UsernameToken>
    </wsse:Security>
  </s:Header>"""

    return SOAP_BODY_TEMPLATE.format(header=header)


async def _post_soap(
    *,
    xaddr: str,
    body: str,
    timeout: float,
) -> tuple[int, str] | None:
    headers = {
        "Content-Type": "application/soap+xml; charset=utf-8",
    }

    session_kwargs = {}
    if urlparse(xaddr).scheme == "https":
        session_kwargs["connector"] = aiohttp.TCPConnector(ssl=False)

    try:
        async with aiohttp.ClientSession(**session_kwargs) as session:
            async with session.post(
                xaddr,
                data=body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                text = await resp.text(errors="ignore")
                return resp.status, text

    except aiohttp.ClientError as e:
        logger.debug(
            "ONVIF GetDeviceInformation HTTP error on %s: %s",
            xaddr,
            e,
        )
        return None

    except Exception:
        logger.exception(
            "ONVIF GetDeviceInformation unexpected error on %s",
            xaddr,
        )
        return None


def _is_not_authorized_fault(text: str) -> bool:
    lowered = text.lower()
    return "notauthorized" in lowered or "not authorized" in lowered


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )

