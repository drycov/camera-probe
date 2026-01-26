# axis.py
from camera_probe.infrastructure.fingerprints.base import Fingerprint


class AxisFingerprint(Fingerprint):
    def match(self, evidence: dict) -> bool:
        if "axis" in (evidence.get("rtsp_vendor_markers") or []):
            return True

        server = (evidence.get("rtsp_server") or "").lower()
        if "axis" in server:
            return True

        m = (evidence.get("onvif_manufacturer") or "").lower()
        if "axis" in m:
            return True

        model = (evidence.get("onvif_model") or "").lower()
        return model.startswith(("p", "q", "m"))

    def vendor(self) -> str:
        return "Axis"

    def confidence(self) -> float:
        return 0.96
