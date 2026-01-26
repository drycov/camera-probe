# camera_probe/devices/mikrotik/fingerprint.py

from __future__ import annotations

from typing import Any, Dict, List

from camera_probe.utils.net_async import tcp_check
from camera_probe.models.mikrotik_signature import MIKROTIK_SIGNATURES


async def fingerprint_mikrotik(ip: str) -> Dict[str, Any]:
    """
    Passive MikroTik fingerprinting via port probing.

    Returns a stable contract:
    {
        confidence: float,
        evidence: dict,
        checked_ports: list[str],
    }
    """

    score: float = 0.0
    checked_ports: List[str] = []
    evidence: Dict[str, Any] = {
        "matched_ports": [],
    }

    for sig in MIKROTIK_SIGNATURES:
        port_id = f"{sig.proto}/{sig.port}"
        checked_ports.append(port_id)

        if sig.proto == "tcp":
            ok = await tcp_check(ip, sig.port, timeout=1.0)
        else:
            # UDP probing (MAC-Winbox / ROMON) — future
            ok = False

        if not ok:
            continue

        evidence["matched_ports"].append(
            {
                "port": sig.port,
                "proto": sig.proto,
                "name": sig.name,
                "weight": sig.weight,
            }
        )
        score += sig.weight

    confidence = min(1.0, score)

    return {
        "confidence": confidence,
        "evidence": evidence if evidence["matched_ports"] else {},
        "checked_ports": checked_ports,
    }
