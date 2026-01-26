# camera_probe/devices/mikrotik/signatures.py

from dataclasses import dataclass


@dataclass(frozen=True)
class PortSignature:
    port: int
    proto: str          # "tcp" | "udp"
    weight: float
    name: str


MIKROTIK_SIGNATURES: list[PortSignature] = [
    PortSignature(8291, "tcp", 0.50, "winbox"),
    PortSignature(9632, "tcp", 0.55, "winbox_custom"),
    PortSignature(8728, "tcp", 0.30, "api"),
    PortSignature(8729, "tcp", 0.35, "api_ssl"),
    PortSignature(22,   "tcp", 0.20, "ssh"),
    PortSignature(80,   "tcp", 0.15, "http"),
    PortSignature(443,  "tcp", 0.15, "https"),
    PortSignature(5678, "udp", 0.40, "mac_winbox"),
    PortSignature(20561,"udp", 0.25, "romon"),
    PortSignature(161,  "udp", 0.20, "snmp"),
]
