# uniview.py
from camera_probe.infrastructure.fingerprints.base import Fingerprint
from camera_probe.infrastructure.fingerprints.utils import EvidenceView


class UniviewFingerprint(Fingerprint):
    def match(self, evidence: dict) -> bool:
        view = EvidenceView(evidence)
        if view.has_marker("rtsp_vendor_markers", "uniview"):
            return True

        manufacturer = view.text("onvif_manufacturer")
        if "uniview" in manufacturer or "unv" in manufacturer:
            return True

        return view.text_startswith("onvif_model", "ipc")

    def vendor(self) -> str:
        return "Uniview"

    def confidence(self) -> float:
        return 0.95
