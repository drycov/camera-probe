from __future__ import annotations

import asyncio
import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _basic_auth_header(username: str, password: str) -> str:
    token = f"{username}:{password}".encode()
    return base64.b64encode(token).decode()


async def rtsp_options_auth(
    *,
    ip: str,
    port: int,
    username: str,
    password: str,
    timeout: float = 1.5,
) -> Optional[str]:
    """
    Send RTSP OPTIONS with Basic Authorization header.
    Returns Server header if present.
    """

    logger.debug(
        "RTSP auth discovery started: ip=%s port=%s user=%s",
        ip,
        port,
        username,
    )

    auth = _basic_auth_header(username, password)

    try:
        logger.trace(
            "Opening RTSP TCP connection (auth) to %s:%s",
            ip,
            port,
        )

        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=timeout,
        )

        request = (
            "OPTIONS rtsp://{ip}:{port}/ RTSP/1.0\r\n"
            "CSeq: 1\r\n"
            "Authorization: Basic {auth}\r\n"
            "\r\n"
        ).format(
            ip=ip,
            port=port,
            auth=auth,
        )

        logger.trace("Sending RTSP OPTIONS (auth) to %s", ip)
        writer.write(request.encode())
        await writer.drain()

        logger.trace("Waiting RTSP auth response from %s", ip)
        data = await asyncio.wait_for(reader.read(2048), timeout=timeout)

        writer.close()
        await writer.wait_closed()
        logger.trace("RTSP auth connection closed for %s", ip)

        text = data.decode(errors="ignore")
        logger.trace("RTSP auth raw response from %s: %r", ip, text)

        # 401 — значит RTSP есть, но креды не приняты (это тоже сигнал)
        if text.startswith("RTSP/1.0 401"):
            logger.debug(
                "RTSP auth rejected (401) on %s",
                ip,
            )
            return None

        for line in text.splitlines():
            if line.lower().startswith("server:"):
                server = line.split(":", 1)[1].strip()
                logger.debug(
                    "RTSP Server header detected (auth) on %s: %s",
                    ip,
                    server,
                )
                return server

        logger.debug(
            "RTSP auth response from %s did not contain Server header",
            ip,
        )

    except asyncio.TimeoutError:
        logger.debug("RTSP auth timeout on %s", ip)

    except ConnectionRefusedError:
        logger.debug("RTSP auth connection refused on %s", ip)

    except Exception:
        logger.exception("Unexpected RTSP auth error on %s", ip)

    return None


async def rtsp_options(ip: str, port: int, timeout: float = 1.5) -> Optional[str]:
    """
    Send RTSP OPTIONS and return Server header if present.
    """

    logger.debug(
        "RTSP discovery started: ip=%s timeout=%.1f",
        ip,
        timeout,
    )

    try:
        logger.trace("Opening RTSP TCP connection to %s:%s", ip, port)
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=timeout,
        )

        request = (
            "OPTIONS rtsp://{ip}:{port}/ RTSP/1.0\r\n" "CSeq: 1\r\n" "\r\n"
        ).format(ip=ip, port=port)

        logger.trace("Sending RTSP OPTIONS to %s", ip)
        writer.write(request.encode())
        await writer.drain()

        logger.trace("Waiting RTSP response from %s", ip)
        data = await asyncio.wait_for(reader.read(1024), timeout=timeout)

        writer.close()
        await writer.wait_closed()
        logger.trace("RTSP connection closed for %s", ip)

        text = data.decode(errors="ignore")
        logger.trace("RTSP raw response from %s: %r", ip, text)

        for line in text.splitlines():
            if line.lower().startswith("server:"):
                server = line.split(":", 1)[1].strip()
                logger.debug(
                    "RTSP Server header detected on %s: %s",
                    ip,
                    server,
                )
                return server

        logger.debug(
            "RTSP response from %s did not contain Server header",
            ip,
        )

    except asyncio.TimeoutError:
        logger.debug("RTSP timeout on %s", ip)

    except ConnectionRefusedError:
        logger.debug("RTSP connection refused on %s", ip)

    except Exception:
        logger.exception("Unexpected RTSP error on %s", ip)

    return None
