# axis.py
from camera_probe.infrastructure.fingerprints.base import Fingerprint
from camera_probe.infrastructure.fingerprints.utils import EvidenceView


class AxisFingerprint(Fingerprint):
    def match(self, evidence: dict) -> bool:
        view = EvidenceView(evidence)
        if view.has_marker("rtsp_vendor_markers", "axis"):
            return True

        if "axis" in view.text("rtsp_server"):
            return True

        if "axis" in view.text("onvif_manufacturer"):
            return True

        return view.text_startswith("onvif_model", ("p", "q", "m"))

    def vendor(self) -> str:
        return "Axis"

    def confidence(self) -> float:
        return 0.96
