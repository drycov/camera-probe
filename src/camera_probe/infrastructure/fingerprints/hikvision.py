# hikvision.py
from camera_probe.infrastructure.fingerprints.base import Fingerprint


class HikvisionFingerprint(Fingerprint):
    def match(self, evidence: dict) -> bool:
        if "hikvision" in (evidence.get("rtsp_vendor_markers") or []):
            return True

        if "hikvision" in (evidence.get("http_vendor_markers") or []):
            return True

        sdp = evidence.get("rtsp_sdp_raw", "").lower()
        if "mediainfo" in sdp:
            return True

        realm = (evidence.get("realm") or "").lower()
        if "hikvision" in realm:
            return True

        m = (evidence.get("onvif_manufacturer") or "").lower()
        return "hikvision" in m

    def vendor(self) -> str:
        return "Hikvision"

    def confidence(self) -> float:
        return 0.97
