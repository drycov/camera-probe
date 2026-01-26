# generic.py
from camera_probe.infrastructure.fingerprints.base import Fingerprint


class GenericRTSPFingerprint(Fingerprint):
    def match(self, evidence: dict) -> bool:
        server = (evidence.get("rtsp_server") or "").lower()
        return any(x in server for x in ("live555", "gstreamer", "vlc"))

    def vendor(self) -> str:
        return "Generic"

    def confidence(self) -> float:
        return 0.60
