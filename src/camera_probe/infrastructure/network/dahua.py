# camera_probe/infrastructure/network/dahua.py

from __future__ import annotations

from typing import Optional

from camera_probe.domain.models.network_info import NetworkInfo
from camera_probe.infrastructure.network.decorators import register_network_extractor
from camera_probe.infrastructure.network.utils import (
    mask_to_cidr,
    gateway_in_subnet,
    subnet_address_cidr,
)


@register_network_extractor("dahua")
class DahuaNetworkExtractor:

    def extract(self, raw: str) -> Optional[NetworkInfo]:
        data: dict[str, str] = {}

        for line in raw.splitlines():
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()

        iface = "eth0"

        ip = data.get("table.Network.eth0.IPAddress")
        mask = data.get("table.Network.eth0.SubnetMask")
        gateway = data.get("table.Network.eth0.DefaultGateway")
        mac = data.get("table.Network.eth0.PhysicalAddress")

        if not ip or not mask:
            return None

        cidr = mask_to_cidr(mask)
        gw_in_subnet = gateway_in_subnet(ip, cidr, gateway)
        subnet = subnet_address_cidr(ip,cidr)
        
        return NetworkInfo(
            interface=iface,
            ip=ip,
            mask=mask,
            cidr=cidr,
            gateway=gateway,
            mac=mac.upper() if mac else None,
            gateway_in_subnet=gw_in_subnet,
            subnet=subnet
        )
