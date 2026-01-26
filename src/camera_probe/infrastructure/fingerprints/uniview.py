# uniview.py
from camera_probe.infrastructure.fingerprints.base import Fingerprint


class UniviewFingerprint(Fingerprint):
    def match(self, evidence: dict) -> bool:
        if "uniview" in (evidence.get("rtsp_vendor_markers") or []):
            return True

        m = (evidence.get("onvif_manufacturer") or "").lower()
        if "uniview" in m or "unv" in m:
            return True

        model = (evidence.get("onvif_model") or "").lower()
        return model.startswith("ipc")

    def vendor(self) -> str:
        return "Uniview"

    def confidence(self) -> float:
        return 0.95
