from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from typing import Dict, Optional, List
from urllib.parse import urljoin

from camera_probe.infrastructure.sdp.parse_sdp import extract_rtsp_vendor_markers, parse_sdp

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Digest helpers
# ──────────────────────────────────────────────


def _parse_digest_challenge(header: str) -> Dict[str, str]:
    params: Dict[str, str] = {}
    for m in re.finditer(r'(\w+)=(?:"([^"]*)"|([^\s,]+))', header):
        params[m.group(1)] = m.group(2) or m.group(3)
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
        f'username="{username}", '
        f'realm="{realm}", '
        f'nonce="{nonce}", '
        f'uri="{uri}", '
        f'response="{response}"'
    )


# ──────────────────────────────────────────────
# RTSP DESCRIBE
# ──────────────────────────────────────────────


async def rtsp_describe(
    ip: str,
    port: int = 554,
    username: str | None = None,
    password: str | None = None,
    timeout: float = 2.5,
) -> Dict[str, str]:
    uri = f"rtsp://{ip}:{port}/"
    evidence: Dict[str, str] = {}

    def build_request(cseq: int, auth: str | None = None) -> str:
        lines = [
            f"DESCRIBE {uri} RTSP/1.0",
            f"CSeq: {cseq}",
            "Accept: application/sdp",
        ]
        if auth:
            lines.append(f"Authorization: {auth}")
        return "\r\n".join(lines) + "\r\n\r\n"

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=timeout,
        )

        async def send(req: str) -> str:
            writer.write(req.encode())
            await writer.drain()
            data = await asyncio.wait_for(reader.read(16384), timeout=timeout)
            return data.decode(errors="ignore")

        cseq = 1

        # ── First DESCRIBE (no auth)
        response = await send(build_request(cseq))
        cseq += 1

        # ── Digest retry (same TCP)
        if (
            "401" in response
            and "www-authenticate" in response.lower()
            and username
            and password
        ):
            m = re.search(
                r"WWW-Authenticate:\s*Digest\s+(.+?)(?:\r\n|$)",
                response,
                re.I,
            )
            if m:
                challenge = _parse_digest_challenge(m.group(1))
                if "realm" in challenge and "nonce" in challenge:
                    auth = _build_digest_authorization(
                        username=username,
                        password=password,
                        realm=challenge["realm"],
                        nonce=challenge["nonce"],
                        method="DESCRIBE",
                        uri=uri,
                    )
                    response = await send(build_request(cseq, auth))
                    cseq += 1

        writer.close()
        await writer.wait_closed()

        # ── Validate response
        if "application/sdp" not in response.lower():
            return evidence

        header, sdp = response.split("\r\n\r\n", 1)
        sdp = sdp.strip()

        evidence["rtsp_sdp_raw"] = sdp

        # Content-Base
        m = re.search(r"^Content-Base:\s*(.+)$", header, re.I | re.M)
        base = m.group(1).strip() if m else uri
        evidence["rtsp_content_base"] = base

        # ── SDP parsing (single source of truth)
        parsed = parse_sdp(sdp)

        session = parsed["session"]
        media = parsed["media"]

        if "s" in session:
            evidence["rtsp_sdp_session"] = session["s"]
        if "o" in session:
            evidence["rtsp_sdp_origin"] = session["o"]
        if "tool" in session:
            evidence["rtsp_sdp_tool"] = session["tool"]

        video = next((m for m in media if m["type"] == "video"), None)
        if not video:
            return evidence

        if video.get("control"):
            evidence["rtsp_track_control"] = video["control"]
            evidence["rtsp_video_track_url"] = urljoin(
                base.rstrip("/") + "/", video["control"].lstrip("/")
            )

        if video["rtpmap"]:
            pt, info = next(iter(video["rtpmap"].items()))
            evidence["rtsp_video_codec"] = info["codec"]

        if video.get("resolution"):
            w, h = video["resolution"]
            evidence["rtsp_video_width"] = str(w)
            evidence["rtsp_video_height"] = str(h)

        if video["vendor_hints"]:
            evidence["vendor_hints"] = ",".join(video["vendor_hints"])
            
        markers = extract_rtsp_vendor_markers(parsed)
        if markers:
            evidence["rtsp_vendor_markers"] = markers

        return evidence

    except Exception as e:
        logger.error("RTSP DESCRIBE error %s:%d → %s", ip, port, e)
        return evidence
