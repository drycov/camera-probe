# hikvision.py
from camera_probe.infrastructure.fingerprints.base import Fingerprint
from camera_probe.infrastructure.fingerprints.utils import EvidenceView


class HikvisionFingerprint(Fingerprint):
    def match(self, evidence: dict) -> bool:
        view = EvidenceView(evidence)
        if view.has_marker("rtsp_vendor_markers", "hikvision"):
            return True

        if view.has_marker("http_vendor_markers", "hikvision"):
            return True

        if view.text_contains("rtsp_sdp_raw", "mediainfo"):
            return True

        if "hikvision" in view.text("realm"):
            return True

        return "hikvision" in view.text("onvif_manufacturer")

    def vendor(self) -> str:
        return "Hikvision"

    def confidence(self) -> float:
        return 0.97
