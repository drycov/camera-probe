# dahua.py
from camera_probe.infrastructure.fingerprints.base import Fingerprint
from camera_probe.infrastructure.fingerprints.utils import EvidenceView


class DahuaFingerprint(Fingerprint):
    def match(self, evidence: dict) -> bool:
        view = EvidenceView(evidence)
        if view.has_marker("rtsp_vendor_markers", "dahua"):
            return True

        if view.has_marker("http_vendor_markers", "dahua"):
            return True

        if view.text_contains("rtsp_sdp_raw", "packetization-supported:dh"):
            return True

        if view.text_contains("url_tried", "magicbox.cgi"):
            return True

        return "dahua" in view.text("onvif_manufacturer")

    def vendor(self) -> str:
        return "Dahua"

    def confidence(self) -> float:
        return 0.97
