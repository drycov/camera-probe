# xiongmai.py
from camera_probe.infrastructure.fingerprints.base import Fingerprint
from camera_probe.infrastructure.fingerprints.utils import EvidenceView


class XiongmaiFingerprint(Fingerprint):
    def match(self, evidence: dict) -> bool:
        view = EvidenceView(evidence)
        if view.has_marker("rtsp_vendor_markers", "xiongmai"):
            return True

        if "xmeye" in view.text("realm"):
            return True

        model = view.text("onvif_model")
        return any(x in model for x in ("xm", "xmeye"))

    def vendor(self) -> str:
        return "Xiongmai"

    def confidence(self) -> float:
        return 0.96
