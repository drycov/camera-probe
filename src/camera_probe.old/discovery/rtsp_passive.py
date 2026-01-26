import asyncio
import contextlib
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

RTSP_DEFAULT_PORT = 554
RTSP_READ_LIMIT = 4096


async def rtsp_options(
    ip: str,
    *,
    port: int = RTSP_DEFAULT_PORT,
    timeout: float = 1.5,
) -> Optional[Dict[str, str]]:
    """
    Sends RTSP OPTIONS request without authentication.

    Used ONLY as passive evidence for vendor detection.
    Never treated as authoritative detection.
    """

    logger.debug(
        "rtsp_options start | ip=%s | port=%d | timeout=%.2fs",
        ip,
        port,
        timeout,
    )

    request = (
        f"OPTIONS rtsp://{ip}:{port}/ RTSP/1.0\r\n"
        "CSeq: 1\r\n"
        "User-Agent: camera_probe/async\r\n"
        "\r\n"
    ).encode()

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=timeout,
        )

        try:
            writer.write(request)
            await writer.drain()

            data = await asyncio.wait_for(
                reader.read(RTSP_READ_LIMIT),
                timeout=timeout,
            )

        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

        if not data:
            logger.debug("rtsp_options empty_response | ip=%s | port=%d", ip, port)
            return None

        headers = _parse_rtsp_headers(data)
        if not headers:
            logger.debug("rtsp_options no_headers | ip=%s | port=%d", ip, port)
            return None

        logger.debug(
            "rtsp_options success | ip=%s | port=%d | headers=%s",
            ip,
            port,
            list(headers.keys()),
        )
        return headers

    except asyncio.TimeoutError:
        logger.debug(
            "rtsp_options timeout | ip=%s | port=%d | timeout=%.2fs",
            ip,
            port,
            timeout,
        )
        return None

    except OSError as e:
        logger.debug(
            "rtsp_options os_error | ip=%s | port=%d | errno=%s",
            ip,
            port,
            e.errno,
        )
        return None

    except Exception:
        logger.exception(
            "rtsp_options unexpected_error | ip=%s | port=%d",
            ip,
            port,
        )
        return None


# ────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────


def _parse_rtsp_headers(data: bytes) -> Dict[str, str]:
    """
    Minimal RTSP header parser.

    RTSP/1.0 200 OK
    Header: Value
    Header2: Value2
    """

    try:
        text = data.decode(errors="ignore")
    except Exception:
        return {}

    lines = text.split("\r\n")
    if not lines or not lines[0].startswith("RTSP/"):
        return {}

    headers: Dict[str, str] = {}

    for line in lines[1:]:
        if not line:
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip()] = value.strip()

    return headers
