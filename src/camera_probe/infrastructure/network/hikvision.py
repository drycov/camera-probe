from __future__ import annotations

import ipaddress
import logging
from typing import Optional

from camera_probe.domain.models.network_info import NetworkInfo
from camera_probe.infrastructure.network.decorators import register_network_extractor
from camera_probe.infrastructure.network.utils import subnet_address_cidr
from camera_probe.infrastructure.xml.parser import parse_xml, extract_default_ns

logger = logging.getLogger(__name__)


@register_network_extractor("hikvision")
class HikvisionNetworkExtractor:
    """
    Extract network information from Hikvision ISAPI XML.

    Correctly handles:
    - multiple NetworkInterface entries
    - deterministic interface selection
    """

    def extract(self, raw: str) -> Optional[NetworkInfo]:
        if not raw:
            return None

        logger.trace("hikvision network raw:\n%s", raw)

        root = parse_xml(raw)
        if root is None:
            return None

        NS = extract_default_ns(root)

        interfaces: list[dict] = []

        # ──────────────────────────────────────────────
        # Collect all interfaces
        # ──────────────────────────────────────────────
        for iface in root.findall(".//ns:NetworkInterface", NS):
            ip_node = iface.find(".//ns:IPAddress", NS)
            if ip_node is None:
                continue

            ip = ip_node.findtext("ns:ipAddress", default=None, namespaces=NS)
            mask = ip_node.findtext("ns:subnetMask", default=None, namespaces=NS)

            gateway = ip_node.findtext(
                "ns:DefaultGateway/ns:ipAddress",
                default=None,
                namespaces=NS,
            )

            mac = iface.findtext(".//ns:MACAddress", default=None, namespaces=NS)
            mac_norm = mac.strip().upper().replace("-", ":") if mac else None

            interfaces.append(
                {
                    "ip": ip,
                    "mask": mask,
                    "gateway": gateway,
                    "mac": mac_norm,
                }
            )

        if not interfaces:
            return None

        # ──────────────────────────────────────────────
        # Select best interface
        # Strategy:
        #   1. interface with default gateway
        #   2. fallback to first interface
        # ──────────────────────────────────────────────
        selected = None
        for iface in interfaces:
            gw = iface.get("gateway")
            if gw and gw != "0.0.0.0":
                selected = iface
                break

        if selected is None:
            selected = interfaces[0]
            logger.debug(
                "hikvision network extractor fallback to first interface | interfaces=%d",
                len(interfaces),
            )

        ip = selected.get("ip")
        mask = selected.get("mask")
        gateway = selected.get("gateway")
        mac = selected.get("mac")

        if not any([ip, mask, gateway, mac]):
            return None

        # ──────────────────────────────────────────────
        # CIDR + gateway check
        # ──────────────────────────────────────────────
        cidr: Optional[int] = None
        gateway_in_subnet: Optional[bool] = None

        if ip and mask:
            try:
                net = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
                cidr = net.prefixlen
                if gateway:
                    gateway_in_subnet = ipaddress.IPv4Address(gateway) in net

                    subnet = subnet_address_cidr(ip, cidr)

            except ValueError:
                cidr = None
                gateway_in_subnet = None
                subnet = None

        return NetworkInfo(
            ip=ip,
            mask=mask,
            cidr=cidr,
            gateway=gateway,
            mac=mac,
            gateway_in_subnet=gateway_in_subnet,
            subnet=subnet,
        )
