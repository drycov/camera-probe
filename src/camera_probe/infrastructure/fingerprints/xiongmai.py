# xiongmai.py
from camera_probe.infrastructure.fingerprints.base import Fingerprint


class XiongmaiFingerprint(Fingerprint):
    def match(self, evidence: dict) -> bool:
        if "xiongmai" in (evidence.get("rtsp_vendor_markers") or []):
            return True

        realm = (evidence.get("realm") or "").lower()
        if "xmeye" in realm:
            return True

        model = (evidence.get("onvif_model") or "").lower()
        return any(x in model for x in ("xm", "xmeye"))

    def vendor(self) -> str:
        return "Xiongmai"

    def confidence(self) -> float:
        return 0.96
