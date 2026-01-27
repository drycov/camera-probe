# camera_probe/infrastructure/network/hikvision.py

from __future__ import annotations

import ipaddress
import xml.etree.ElementTree as ET
from typing import Optional

from camera_probe.domain.models.network_info import NetworkInfo
from camera_probe.infrastructure.network.decorators import register_network_extractor


@register_network_extractor("hikvision")
class HikvisionNetworkExtractor:
    """
    ISAPI XML network parser.
    """

    NS = {"ns": "http://www.hikvision.com/ver20/XMLSchema"}

    def extract(self, raw: str) -> Optional[NetworkInfo]:
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return None

        iface = root.find(".//ns:NetworkInterface", self.NS)
        if iface is None:
            return None

        ip_node = iface.find(".//ns:IPAddress", self.NS)
        if ip_node is None:
            return None

        ip = ip_node.findtext("ns:ipAddress", namespaces=self.NS)
        mask = ip_node.findtext("ns:subnetMask", namespaces=self.NS)

        gw_node = ip_node.find("ns:DefaultGateway/ns:ipAddress", self.NS)
        gateway = gw_node.text if gw_node is not None else None

        mac = iface.findtext(".//ns:MACAddress", namespaces=self.NS)
        iface_name = iface.findtext("ns:id", namespaces=self.NS) or "eth0"

        if not ip or not mask:
            return None

        net = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
        cidr = net.prefixlen

        gateway_in_subnet = None
        if gateway:
            gateway_in_subnet = ipaddress.IPv4Address(gateway) in net

        return NetworkInfo(
            interface=iface_name,
            ip=ip,
            mask=mask,
            cidr=cidr,
            gateway=gateway,
            mac=mac.upper().replace("-", ":") if mac else None,
            gateway_in_subnet=gateway_in_subnet,
        )
