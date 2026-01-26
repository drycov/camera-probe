# camera_probe/application/policies/confidence_policy.py
def is_probe_success(confidence: float, min_confidence: float) -> bool:
    return confidence >= min_confidence
