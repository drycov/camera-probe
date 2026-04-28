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

    def __init__(self, target_ip: str | None = None) -> None:
        self._target_ip = target_ip

    def extract(self, raw: str) -> Optional[NetworkInfo]:
        if not raw:
            return None

        logger.trace("hikvision network raw:\n%s", raw)

        root = parse_xml(raw)
        if root is None:
            return None

        NS = extract_default_ns(root)
        if root.tag.endswith("BondList") or root.tag.endswith("Bond"):
            return self._extract_bond(root, NS)

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

        selected = self._select_interface(interfaces)
        if selected is None:
            logger.debug(
                "hikvision network extractor could not determine canonical interface | target=%s interfaces=%d",
                self._target_ip,
                len(interfaces),
            )
            return None

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

    def _extract_bond(self, root, ns: dict[str, str]) -> Optional[NetworkInfo]:
        bond = root.find(".//ns:Bond", ns) if ns else root.find(".//Bond")
        if bond is None and root.tag.endswith("Bond"):
            bond = root
        if bond is None:
            return None

        enabled = self._findtext(bond, ns, "enabled", "enable")
        if enabled and enabled.strip().lower() != "true":
            logger.debug("hikvision bond endpoint present but disabled")
            return None

        ip = self._findtext(bond, ns, "ipAddress")
        mask = self._findtext(bond, ns, "subnetMask")
        gateway = self._find_nested_ip(bond, ns, "DefaultGateway")
        mac = self._findtext(bond, ns, "MACAddress", "macAddress")
        mac = mac.strip().upper().replace("-", ":") if mac else None

        if not any([ip, mask, gateway, mac]):
            return None

        cidr: Optional[int] = None
        gateway_in_subnet: Optional[bool] = None
        subnet: Optional[str] = None

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

        logger.debug(
            "hikvision network extractor selected bond endpoint | target=%s ip=%s",
            self._target_ip,
            ip,
        )

        return NetworkInfo(
            ip=ip,
            mask=mask,
            cidr=cidr,
            gateway=gateway,
            mac=mac,
            gateway_in_subnet=gateway_in_subnet,
            subnet=subnet,
        )

    def _select_interface(self, interfaces: list[dict]) -> Optional[dict]:
        if self._target_ip:
            for iface in interfaces:
                if iface.get("ip") == self._target_ip:
                    logger.debug(
                        "hikvision network extractor matched target ip | target=%s",
                        self._target_ip,
                    )
                    return iface

            for iface in interfaces:
                ip = iface.get("ip")
                mask = iface.get("mask")
                if not ip or not mask:
                    continue
                try:
                    net = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
                    if ipaddress.IPv4Address(self._target_ip) in net:
                        logger.debug(
                            "hikvision network extractor matched target subnet | target=%s subnet=%s",
                            self._target_ip,
                            net,
                        )
                        return iface
                except ValueError:
                    continue

            if len(interfaces) > 1:
                return None

            logger.debug(
                "hikvision network extractor single-interface fallback without target match | target=%s",
                self._target_ip,
            )
            return interfaces[0]

        for iface in interfaces:
            gw = iface.get("gateway")
            if gw and gw != "0.0.0.0":
                logger.debug(
                    "hikvision network extractor selected gateway interface | gateway=%s",
                    gw,
                )
                return iface

        logger.debug(
            "hikvision network extractor fallback to first interface | interfaces=%d",
            len(interfaces),
        )
        return interfaces[0]

    @staticmethod
    def _findtext(node, ns: dict[str, str], *tags: str) -> Optional[str]:
        for tag in tags:
            if ns:
                el = node.find(f".//ns:{tag}", ns)
                if el is not None and el.text:
                    return el.text.strip()
            el = node.find(f".//{tag}")
            if el is not None and el.text:
                return el.text.strip()
        return None

    @classmethod
    def _find_nested_ip(cls, node, ns: dict[str, str], container_tag: str) -> Optional[str]:
        if ns:
            container = node.find(f".//ns:{container_tag}", ns)
            if container is not None:
                value = cls._findtext(container, ns, "ipAddress")
                if value:
                    return value

        container = node.find(f".//{container_tag}")
        if container is not None:
            return cls._findtext(container, {}, "ipAddress")

        return None
