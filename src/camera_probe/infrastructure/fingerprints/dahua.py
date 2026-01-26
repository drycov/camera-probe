# dahua.py
from camera_probe.infrastructure.fingerprints.base import Fingerprint


class DahuaFingerprint(Fingerprint):
    def match(self, evidence: dict) -> bool:
        if "dahua" in (evidence.get("rtsp_vendor_markers") or []):
            return True

        if "dahua" in (evidence.get("http_vendor_markers") or []):
            return True

        if "packetization-supported:dh" in evidence.get("rtsp_sdp_raw", "").lower():
            return True

        if "magicbox.cgi" in evidence.get("url_tried", "").lower():
            return True

        m = (evidence.get("onvif_manufacturer") or "").lower()
        return "dahua" in m

    def vendor(self) -> str:
        return "Dahua"

    def confidence(self) -> float:
        return 0.97
