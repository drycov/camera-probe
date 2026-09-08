from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from typing import Dict
from urllib.parse import urljoin

from camera_probe.infrastructure.sdp.parse_sdp import extract_rtsp_vendor_markers, parse_sdp

logger = logging.getLogger(__name__)


def _parse_digest_challenge(header: str) -> Dict[str, str]:
    params: Dict[str, str] = {}
    for match in re.finditer(r'(\w+)=(?:"([^"]*)"|([^\s,]+))', header):
        params[match.group(1).lower()] = match.group(2) or match.group(3)
    return params


def _build_digest_authorization(
    username: str,
    password: str,
    realm: str,
    nonce: str,
    method: str,
    uri: str,
) -> str:
    ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest()
    ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
    response = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
    return (
        "Digest "
        f'username="{username}", realm="{realm}", nonce="{nonce}", '
        f'uri="{uri}", response="{response}"'
    )


async def rtsp_describe(
    ip: str,
    port: int = 554,
    username: str | None = None,
    password: str | None = None,
    timeout: float = 2.5,
) -> Dict[str, object]:
    """Fetch one RTSP SDP using a single hard deadline.

    The socket is always closed, including timeout/cancellation/error paths.
    Only one DESCRIBE connection is attempted by the discovery engine, so this
    function must remain cheap and deterministic.
    """
    uri = f"rtsp://{ip}:{port}/"
    evidence: Dict[str, object] = {}
    timeout = max(0.05, timeout)
    deadline = time.monotonic() + timeout
    writer = None

    def build_request(cseq: int, auth: str | None = None) -> str:
        lines = [
            f"DESCRIBE {uri} RTSP/1.0",
            f"CSeq: {cseq}",
            "Accept: application/sdp",
        ]
        if auth:
            lines.append(f"Authorization: {auth}")
        return "\r\n".join(lines) + "\r\n\r\n"

    async def send(request: str) -> str:
        remaining = max(0.01, deadline - time.monotonic())
        writer.write(request.encode())
        await asyncio.wait_for(writer.drain(), timeout=remaining)
        remaining = max(0.01, deadline - time.monotonic())
        data = await asyncio.wait_for(writer_read(reader), timeout=remaining)
        return data.decode(errors="ignore")

    async def writer_read(reader) -> bytes:
        return await reader.read(16384)

    try:
        remaining = max(0.01, deadline - time.monotonic())
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port), timeout=remaining
        )

        response = await send(build_request(1))

        if (
            "401" in response
            and "www-authenticate" in response.lower()
            and username
            and password
        ):
            match = re.search(
                r"WWW-Authenticate:\s*Digest\s+(.+?)(?:\r\n|$)",
                response,
                re.I,
            )
            if match:
                challenge = _parse_digest_challenge(match.group(1))
                realm = challenge.get("realm")
                nonce = challenge.get("nonce")
                if realm and nonce and time.monotonic() < deadline:
                    auth = _build_digest_authorization(
                        username=username,
                        password=password,
                        realm=realm,
                        nonce=nonce,
                        method="DESCRIBE",
                        uri=uri,
                    )
                    response = await send(build_request(2, auth))

        if "application/sdp" not in response.lower():
            return evidence

        parts = re.split(r"\r\n\r\n", response, maxsplit=1)
        if len(parts) != 2:
            return evidence
        header, sdp = parts
        sdp = sdp.strip()
        evidence["rtsp_sdp_raw"] = sdp

        match = re.search(r"^Content-Base:\s*(.+)$", header, re.I | re.M)
        base = match.group(1).strip() if match else uri
        evidence["rtsp_content_base"] = base

        parsed = parse_sdp(sdp)
        evidence["rtsp_sdp_parsed"] = parsed

        session = parsed.get("session", {})
        media = parsed.get("media", [])
        if "s" in session:
            evidence["rtsp_sdp_session"] = session["s"]
        if "o" in session:
            evidence["rtsp_sdp_origin"] = session["o"]
        if "tool" in session:
            evidence["rtsp_sdp_tool"] = session["tool"]

        video = next((item for item in media if item.get("type") == "video"), None)
        if not video:
            return evidence

        if video.get("control"):
            evidence["rtsp_track_control"] = video["control"]
            evidence["rtsp_video_track_url"] = urljoin(
                base.rstrip("/") + "/", video["control"].lstrip("/")
            )

        if video.get("rtpmap"):
            _, info = next(iter(video["rtpmap"].items()))
            evidence["rtsp_video_codec"] = info["codec"]

        if video.get("resolution"):
            width, height = video["resolution"]
            evidence["rtsp_video_width"] = str(width)
            evidence["rtsp_video_height"] = str(height)

        if video.get("vendor_hints"):
            evidence["vendor_hints"] = ",".join(video["vendor_hints"])

        markers = extract_rtsp_vendor_markers(parsed)
        if markers:
            evidence["rtsp_vendor_markers"] = markers

        return evidence
    except asyncio.CancelledError:
        raise
    except asyncio.TimeoutError:
        logger.debug("RTSP DESCRIBE timeout | ip=%s port=%s", ip, port)
    except Exception as exc:
        logger.debug(
            "RTSP DESCRIBE failed | ip=%s port=%s | error=%s",
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

    return evidence
