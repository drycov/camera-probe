# camera_probe/infrastructure/discovery/onvif.py
from __future__ import annotations

import asyncio
import logging
import socket
import uuid
from typing import Dict

logger = logging.getLogger(__name__)

ONVIF_MULTICAST = ("239.255.255.250", 3702)


def _build_probe_message() -> bytes:
    message_id = uuid.uuid4()
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"
            xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"
            xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery">
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

        if "XAddrs>" in text:
            start = text.find("XAddrs>") + 7
            end = text.find("</", start)
            evidence["onvif_xaddr"] = text[start:end].strip()

        if "Manufacturer>" in text:
            start = text.find("Manufacturer>") + 13
            end = text.find("</", start)
            evidence["manufacturer"] = text[start:end].strip()

        if "Model>" in text:
            start = text.find("Model>") + 6
            end = text.find("</", start)
            evidence["model"] = text[start:end].strip()

        logger.debug("ONVIF evidence collected for %s: %s", ip, evidence)
        return evidence

    except Exception:
        logger.exception("ONVIF discovery failed for %s", ip)

    finally:
        sock.close()

    return {}
