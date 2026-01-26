from typing import Dict, List, Optional, Set


def parse_sdp(sdp: str) -> Dict:
    session: Dict[str, object] = {
        "vendor_hints": set(),  # ← ВАЖНО
    }
    media: List[Dict] = []

    current: Optional[Dict] = None

    def new_media(parts: List[str]) -> Dict:
        return {
            "type": parts[0],
            "payloads": parts[3:],
            "control": None,
            "rtpmap": {},
            "fmtp": {},
            "resolution": None,
            "vendor_hints": set(),
        }

    for raw in sdp.splitlines():
        line = raw.strip()
        if not line or "=" not in line:
            continue

        key, value = line.split("=", 1)
        value_lower = value.lower()

        # ───── Session level ─────
        if current is None:
            if key == "s":
                session["s"] = value
                continue

            if key == "o":
                session["o"] = value
                continue

            if key == "a":
                if value.startswith("tool:"):
                    session["tool"] = value.split(":", 1)[1]

                # ✅ Dahua markers (SESSION!)
                if value_lower in {
                    "packetization-supported:dh",
                    "rtppayload-supported:dh",
                }:
                    session["vendor_hints"].add("dahua")

                # Hikvision
                if "mediainfo" in value_lower:
                    session["vendor_hints"].add("hikvision")

        # ───── Media start ─────
        if key == "m":
            parts = value.split()
            if len(parts) >= 4:
                current = new_media(parts)
                media.append(current)
            continue

        # ───── Media attributes ─────
        if key != "a" or current is None:
            continue

        if value.startswith("control:"):
            current["control"] = value.split(":", 1)[1]
            continue

        if value.startswith("rtpmap:"):
            try:
                pt, rest = value[7:].split(None, 1)
                codec, _ = rest.split("/", 1)
                codec = codec.upper()
                if codec in {"HEVC", "H265"}:
                    codec = "H265"
                current["rtpmap"][pt] = {"codec": codec}
            except ValueError:
                pass
            continue

        if value.startswith("fmtp:"):
            try:
                pt, params = value[5:].split(None, 1)
                for p in params.split(";"):
                    if p.startswith("x-dimensions="):
                        w, h = p.split("=", 1)[1].split(",", 1)
                        current["resolution"] = (int(w), int(h))
                        current["vendor_hints"].add("dahua")
            except ValueError:
                pass
            continue

        if "mediainfo" in value_lower:
            current["vendor_hints"].add("hikvision")

    # normalize
    session["vendor_hints"] = sorted(session["vendor_hints"])
    for m in media:
        m["vendor_hints"] = sorted(m["vendor_hints"])

    return {
        "session": session,
        "media": media,
    }

def extract_rtsp_vendor_markers(parsed: Dict) -> List[str]:
    markers = set()

    markers.update(parsed["session"].get("vendor_hints", []))
    for m in parsed.get("media", []):
        markers.update(m.get("vendor_hints", []))

    return sorted(markers)


def aggregate_rtsp_vendor_markers(parsed_sdp: Dict) -> List[str]:
    markers: Set[str] = set()

    # session-level
    session = parsed_sdp.get("session", {})
    markers.update(session.get("vendor_hints", []))

    # media-level
    for m in parsed_sdp.get("media", []):
        markers.update(m.get("vendor_hints", []))

    return sorted(markers)
