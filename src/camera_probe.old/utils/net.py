# camera_probe/utils/net.py
from __future__ import annotations

from ipaddress import ip_network
from typing import Iterable


def iter_subnet_hosts(subnet: str) -> Iterable[str]:
    """
    Iterate over usable host IPs in a subnet.

    Example:
        iter_subnet_hosts("10.165.64.0/29")
    """
    net = ip_network(subnet, strict=False)
    for host in net.hosts():
        yield str(host)
