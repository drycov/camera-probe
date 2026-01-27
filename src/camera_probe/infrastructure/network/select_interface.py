from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
from typing import Iterable, Optional


def select_interface(
    interfaces: Iterable[dict],
    *,
    probe_ip: Optional[str],
) -> Optional[dict]:
    """
    Select best matching network interface.

    Interface dict keys:
      - ip
      - mask
      - gateway
      - mac
    """

    interfaces = list(interfaces)
    if not interfaces:
        return None

    # 1️⃣ exact IP match
    if probe_ip:
        for iface in interfaces:
            if iface.get("ip") == probe_ip:
                return iface

    # 2️⃣ probe IP inside subnet
    if probe_ip:
        try:
            probe_addr = IPv4Address(probe_ip)
        except ValueError:
            probe_addr = None

        if probe_addr:
            for iface in interfaces:
                ip = iface.get("ip")
                mask = iface.get("mask")
                if not ip or not mask:
                    continue
                try:
                    net = IPv4Network(f"{ip}/{mask}", strict=False)
                except ValueError:
                    continue
                if probe_addr in net:
                    return iface

    # 3️⃣ has default gateway
    for iface in interfaces:
        gw = iface.get("gateway")
        if gw and gw != "0.0.0.0":
            return iface

    # 4️⃣ fallback
    return interfaces[0]
