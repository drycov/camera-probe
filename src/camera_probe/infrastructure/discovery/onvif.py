# camera_probe/infrastructure/discovery/onvif.py
from __future__ import annotations

import asyncio
import logging
import socket
import uuid
from typing import Dict
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

ONVIF_MULTICAST = ("239.255.255.250", 3702)
ONVIF_NAMESPACES = {
    "soap-env": "http://www.w3.org/2003/05/soap-envelope",
    "wsa": "http://schemas.xmlsoap.org/ws/2004/08/addressing",
    "d": "http://schemas.xmlsoap.org/ws/2005/04/discovery",
    "dn": "http://www.onvif.org/ver10/network/wsdl",
}


def _build_probe_message() -> bytes:
    message_id = uuid.uuid4()
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"
            xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"
            xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
            xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
  <e:Header>
    <w:MessageID>uuid:{message_id}</w:MessageID>
    <w:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>
    <w:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>
  </e:Header>
  <e:Body>
    <d:Probe>
      <d:Types>dn:NetworkVideoTransmitter</d:Types>
    </d:Probe>
  </e:Body>
</e:Envelope>
""".encode("utf-8")


async def onvif_probe(
    ip: str,
    timeout: float = 2.0,
) -> Dict[str, str]:
    """
    Perform ONVIF WS-Discovery probe.
    Returns evidence dict (empty if not ONVIF).
    """

    logger.debug("ONVIF discovery started for %s", ip)

    loop = asyncio.get_running_loop()
    evidence: Dict[str, str] = {}

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setblocking(False)

    try:
        probe = _build_probe_message()

        logger.trace("Sending ONVIF Probe to %s", ONVIF_MULTICAST)
        sock.sendto(probe, ONVIF_MULTICAST)

        try:
            data, addr = await asyncio.wait_for(
                loop.sock_recvfrom(sock, 65535),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.debug("ONVIF discovery timeout for %s", ip)
            return {}

        src_ip, _ = addr
        if src_ip != ip:
            logger.trace(
                "ONVIF response from %s ignored (expecting %s)",
                src_ip,
                ip,
            )
            return {}

        text = data.decode(errors="ignore")
        logger.trace("ONVIF response from %s: %s", ip, text)

        evidence["onvif"] = "true"
        evidence.update(_parse_probe_match(text))

        if not evidence.get("onvif_xaddrs") and not evidence.get("onvif_xaddr"):
            logger.debug("ONVIF response did not contain XAddrs for %s", ip)

        logger.debug("ONVIF evidence collected for %s: %s", ip, evidence)
        return evidence

    except Exception:
        logger.exception("ONVIF discovery failed for %s", ip)

    finally:
        sock.close()

    return {}


def _parse_probe_match(text: str) -> Dict[str, str]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return {}

    evidence: Dict[str, str] = {}

    xaddrs = _find_text(root, "XAddrs")
    if xaddrs:
        items = [item.strip() for item in xaddrs.split() if item.strip()]
        if items:
            evidence["onvif_xaddr"] = items[0]
            evidence["onvif_xaddrs"] = " ".join(items)

    scopes = _find_text(root, "Scopes")
    if scopes:
        evidence["onvif_scopes"] = scopes

    types = _find_text(root, "Types")
    if types:
        evidence["onvif_types"] = types

    return evidence


def _find_text(root: ET.Element, tag_suffix: str) -> str | None:
    for element in root.iter():
        if element.tag.endswith(tag_suffix) and element.text:
            return element.text.strip()
    return None
