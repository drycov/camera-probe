from __future__ import annotations

import asyncio
import base64
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


def _basic_auth_header(username: str, password: str) -> str:
    token = f"{username}:{password}".encode()
    return base64.b64encode(token).decode()


async def _send_options(
    *,
    ip: str,
    port: int,
    timeout: float,
    auth_header: str | None = None,
) -> Optional[str]:
    """Send one OPTIONS request with one hard deadline and guaranteed close."""
    timeout = max(0.05, timeout)
    deadline = time.monotonic() + timeout
    writer = None

    try:
        remaining = max(0.01, deadline - time.monotonic())
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port), timeout=remaining
        )

        lines = [
            f"OPTIONS rtsp://{ip}:{port}/ RTSP/1.0",
            "CSeq: 1",
        ]
        if auth_header:
            lines.append(f"Authorization: Basic {auth_header}")
        writer.write(("\r\n".join(lines) + "\r\n\r\n").encode())
        remaining = max(0.01, deadline - time.monotonic())
        await asyncio.wait_for(writer.drain(), timeout=remaining)

        remaining = max(0.01, deadline - time.monotonic())
        data = await asyncio.wait_for(reader.read(2048), timeout=remaining)
        text = data.decode(errors="ignore")

        for line in text.splitlines():
            if line.lower().startswith("server:"):
                return line.split(":", 1)[1].strip()
        return None
    except asyncio.CancelledError:
        raise
    except asyncio.TimeoutError:
        logger.debug("RTSP OPTIONS timeout | ip=%s port=%s", ip, port)
    except ConnectionRefusedError:
        logger.debug("RTSP OPTIONS connection refused | ip=%s port=%s", ip, port)
    except Exception as exc:
        logger.debug(
            "RTSP OPTIONS failed | ip=%s port=%s | error=%s",
            ip,
            port,
            type(exc).__name__,
        )
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
    return None


async def rtsp_options_auth(
    *,
    ip: str,
    port: int,
    username: str,
    password: str,
    timeout: float = 1.5,
) -> Optional[str]:
    """Send RTSP OPTIONS with Basic Authorization."""
    logger.debug("RTSP auth discovery started: ip=%s port=%s", ip, port)
    return await _send_options(
        ip=ip,
        port=port,
        timeout=timeout,
        auth_header=_basic_auth_header(username, password),
    )


async def rtsp_options(ip: str, port: int, timeout: float = 1.5) -> Optional[str]:
    """Send RTSP OPTIONS and return the Server header if present."""
    logger.debug("RTSP discovery started: ip=%s port=%s timeout=%.1f", ip, port, timeout)
    return await _send_options(ip=ip, port=port, timeout=timeout)
