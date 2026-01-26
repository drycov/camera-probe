from __future__ import annotations

import asyncio
import logging
from typing import Final, Any, Dict, Optional

import aiohttp

from camera_probe.adapters.base import CameraAdapter
from camera_probe.adapters.registry import AdapterRegistry
from camera_probe.clients.registry import ClientRegistry
from camera_probe.models.detect_result import DetectResult
from camera_probe.models.probe_result import ProbeResult, NetworkInfo, NtpInfo

logger = logging.getLogger(__name__)


@AdapterRegistry.register
class HikvisionAdapter(CameraAdapter):
    """
    Discovery + probe adapter for Hikvision cameras (ISAPI).
    """

    vendor: Final[str] = "hikvision"

    HIKVISION_MARKERS = ("HIKVISION", "DS-", "HIK")
    BLACKLIST_SUBSTRINGS = ("XM", "NETSURVEILLANCE", "H.264")

    # ------------------------------------------------------------------ detect

    @classmethod
    async def detect_async(
        cls,
        ip: str,
        *,
        timeout: float = 3.0,
        **_: Any,
    ) -> DetectResult:
        url = f"http://{ip}/"
        evidence: Dict[str, Any] = {
            "method": "http_root_probe",
            "url": url,
            "timeout": timeout,
        }

        logger.debug("hikvision detect → start | ip=%s", ip)

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as session:
                async with session.get(url, allow_redirects=True) as resp:
                    evidence["status"] = resp.status

                    if resp.status != 200:
                        return cls._no_match(ip, evidence, f"http_{resp.status}")

                    body = await resp.text(errors="ignore")
                    upper = body.upper()
                    evidence["body_preview"] = body[:300]

                    if any(b in upper for b in cls.BLACKLIST_SUBSTRINGS):
                        return cls._no_match(ip, evidence, "blacklisted")

                    matches = [m for m in cls.HIKVISION_MARKERS if m in upper]
                    confidence = min(0.96, 0.4 + len(matches) * 0.25)

                    if confidence < 0.65:
                        return cls._no_match(ip, evidence, "no_strong_markers")

                    evidence["matched_markers"] = matches

                    return DetectResult(
                        ip=ip,
                        vendor=cls.vendor,
                        adapter_cls=cls,
                        confidence=confidence,
                        status="matched",
                        evidence=evidence,
                    )

        except Exception as exc:
            evidence["error"] = str(exc)
            logger.warning("hikvision detect → error | ip=%s | %s", ip, exc)
            return DetectResult(
                ip=ip,
                vendor=None,
                adapter_cls=None,
                confidence=0.0,
                status="error",
                evidence=evidence,
                error=str(exc),
            )

    @staticmethod
    def _no_match(ip: str, evidence: Dict[str, Any], reason: str) -> DetectResult:
        evidence["reason"] = reason
        return DetectResult(
            ip=ip,
            vendor=None,
            adapter_cls=None,
            confidence=0.0,
            status="no_match",
            evidence=evidence,
        )

    # ------------------------------------------------------------------ init

    def __init__(
        self,
        ip: str,
        *,
        username: str = "",
        password: str = "",
        timeout: float = 5.0,
        try_anonymous: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            ip=ip,
            username=username,
            password=password,
            timeout=timeout,
            **kwargs,
        )

        self.try_anonymous: Final[bool] = try_anonymous

        client_cls = ClientRegistry.get(self.vendor)
        if client_cls is None:
            raise RuntimeError(
                f"No client registered for vendor '{self.vendor}'"
            )

        self.client = client_cls(
            ip=ip,
            username=username,
            password=password,
            timeout=timeout,
            try_anonymous=try_anonymous,
        )

        logger.debug(
            "HikvisionAdapter init | ip=%s | timeout=%.1fs | try_anonymous=%s",
            ip, timeout, try_anonymous,
        )

    # ------------------------------------------------------------------ probe

    async def probe_async(self) -> ProbeResult:
        logger.info(
            "hikvision probe → start | ip=%s | creds=%s",
            self.ip,
            bool(self.username or self.password),
        )

        try:
            tasks = {
                "device": self.client.get_device_info(),
                "network": self.client.get_network_info(),
                "ntp": self.client.get_ntp_info(),
            }

            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            data = dict(zip(tasks.keys(), results))

            errors: list[str] = []

            def pick(key: str):
                val = data.get(key)
                if isinstance(val, Exception):
                    errors.append(f"{key}: {type(val).__name__}")
                    return None
                return val

            device = pick("device") or {}
            net_raw = pick("network")
            ntp_raw = pick("ntp")

            # ─── identity ───
            model = device.get("model")
            serial = device.get("serialNumber") or device.get("serial")
            mac = device.get("macAddress") or device.get("mac")
            firmware = device.get("firmwareVersion") or device.get("firmware")

            # ─── network ───
            network: Optional[NetworkInfo] = None
            logger.info(net_raw)
            if isinstance(net_raw, dict):
                network = NetworkInfo(
                    ip=net_raw.get("ip"),
                    netmask=net_raw.get("mask"),
                    cidr=net_raw.get("cidr"),
                    gateway=net_raw.get("gateway"),
                    gateway_in_subnet=net_raw.get("gateway_in_subnet"),
                    # mac=net_raw.get("mac"),
                )

            # ─── ntp ───
            ntp: Optional[NtpInfo] = None
            if isinstance(ntp_raw, dict):
                ntp = NtpInfo(
                    enabled=bool(ntp_raw.get("enabled")),
                    server=ntp_raw.get("server"),
                    timezone=ntp_raw.get("timezone"),
                    update_period=ntp_raw.get("updatePeriod"),
                    port=ntp_raw.get("port"),
                    interval=ntp_raw.get("interval"),
                )

            identity_ok = bool(serial or model or mac)
            confidence = (
                1.0 if serial and model
                else 0.85 if model and mac
                else 0.75 if model or mac
                else 0.4
            )

            return ProbeResult(
                ip=self.ip,
                vendor=self.vendor,
                model=model,
                serial=serial,
                mac=mac,
                firmware=firmware,
                network=network,
                ntp=ntp,
                confidence=confidence,
                error=", ".join(errors) if errors else None,
                raw={
                    "source": "hikvision_isapi",
                    "partial_errors": errors or None,
                },
            )

        except Exception as exc:
            logger.exception("hikvision probe → critical failure | ip=%s", self.ip)
            return ProbeResult(
                ip=self.ip,
                vendor=self.vendor,
                confidence=0.0,
                error=f"critical:{type(exc).__name__}",
                raw={
                    "exception": str(exc),
                    "source": "hikvision_isapi",
                },
            )
