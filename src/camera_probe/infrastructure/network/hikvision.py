# camera_probe/infrastructure/network/hikvision.py

from __future__ import annotations

import ipaddress
from typing import Optional

from camera_probe.domain.models.network_info import NetworkInfo
from camera_probe.domain.ports.network_extractor import NetworkExtractor
from camera_probe.infrastructure.network.decorators import register_network_extractor
from camera_probe.infrastructure.xml.parser import extract_default_ns, parse_xml
import logging
logger = logging.getLogger(__name__)

@register_network_extractor("hikvision")
class HikvisionNetworkExtractor:
    def extract(self, raw: str) -> Optional[NetworkInfo]:
        if not raw:
            return None

        root = parse_xml(raw)
        if root is None:
            return None

        NS = extract_default_ns(root)

        # root может быть сразу <NetworkInterface>
        if root.tag.endswith("NetworkInterface"):
            iface = root
        else:
            iface = root.find(".//ns:NetworkInterface", NS)

        if iface is None:
            return None

        ip_node = iface.find(".//ns:IPAddress", NS)
        if ip_node is None:
            return None

        ip = ip_node.findtext("ns:ipAddress", default=None, namespaces=NS)
        mask = ip_node.findtext("ns:subnetMask", default=None, namespaces=NS)

        gateway = ip_node.findtext("ns:DefaultGateway/ns:ipAddress", default=None, namespaces=NS)

        mac = iface.findtext(".//ns:MACAddress", default=None, namespaces=NS)

        # ничего полезного не нашли
        if not any([ip, mask, gateway, mac]):
            return None

        cidr: Optional[int] = None
        gateway_in_subnet: Optional[bool] = None

        if ip and mask:
            try:
                net = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
                cidr = net.prefixlen
                if gateway:
                    gateway_in_subnet = ipaddress.IPv4Address(gateway) in net
            except ValueError:
                # некорректные ip/mask/gw — просто не считаем cidr/subnet-check
                cidr = None
                gateway_in_subnet = None

        mac_norm = None
        if mac:
            mac_norm = mac.strip().upper().replace("-", ":")

        return NetworkInfo(
            ip=ip,
            mask=mask,
            cidr=cidr,
            gateway=gateway,
            gateway_in_subnet=gateway_in_subnet,
            mac=mac_norm,
        )
