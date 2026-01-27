# generic.py
from camera_probe.infrastructure.fingerprints.base import Fingerprint
from camera_probe.infrastructure.fingerprints.utils import EvidenceView


class GenericRTSPFingerprint(Fingerprint):
    def match(self, evidence: dict) -> bool:
        view = EvidenceView(evidence)
        return any(
            token in view.text("rtsp_server")
            for token in ("live555", "gstreamer", "vlc")
        )

    def vendor(self) -> str:
        return "Generic"

    def confidence(self) -> float:
        return 0.60
