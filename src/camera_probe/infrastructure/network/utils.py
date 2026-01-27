# camera_probe/infrastructure/network/utils.py

from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
from typing import Optional


def mask_to_cidr(mask: str) -> Optional[int]:
    try:
        return IPv4Network(f"0.0.0.0/{mask}").prefixlen
    except Exception:
        return None


def gateway_in_subnet(
    ip: str,
    cidr: Optional[int],
    gateway: Optional[str],
) -> Optional[bool]:
    if not cidr or not gateway:
        return None

    try:
        net = IPv4Network(f"{ip}/{cidr}", strict=False)
        return IPv4Address(gateway) in net
    except Exception:
        return None


def subnet_address_cidr(ip: str, cidr: int) -> str:
    network = IPv4Network(f"{ip}/{cidr}", strict=False)
    subnet = f"{str(network.network_address)}/{cidr}"
    return str(subnet)
