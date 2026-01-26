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
class AxisAdapter(CameraAdapter):
    """
    Discovery + probe adapter for Axis cameras (VAPIX).
    """

    vendor: Final[str] = "axis"

    AXIS_MARKERS = frozenset(
        {
            "AXIS",
            "AXIS COMMUNICATIONS",
            "PRODNBR",
            "PRODFULLNAME",
            "AXIS M",
            "AXIS P",
            "AXIS Q",
            "AXIS V",
            "AXIS COMPANION",
        }
    )

    BLACKLIST = frozenset(
        {
            "H.264",
            "NETSURVEILLANCE",
            "XM",
            "HIKVISION",
            "DAHUA",
            "IMOU",
        }
    )

    # ------------------------------------------------------------------ detect

    @classmethod
    async def detect_async(
        cls,
        ip: str,
        *,
        timeout: float = 3.0,
        **_: Any,
    ) -> DetectResult:
        url = f"http://{ip}/axis-cgi/basicdeviceinfo.cgi"
        evidence: Dict[str, Any] = {
            "method": "basicdeviceinfo.cgi",
            "url": url,
            "timeout": timeout,
        }

        logger.debug("axis detect → start | ip=%s", ip)

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

                    if any(b in upper for b in cls.BLACKLIST):
                        return cls._no_match(ip, evidence, "blacklisted")

                    matches = [m for m in cls.AXIS_MARKERS if m in upper]
                    confidence = min(0.98, 0.4 + len(matches) * 0.25)

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
            logger.warning("axis detect → error | ip=%s | %s", ip, exc)
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
        timeout: float = 6.0,
        preferred_proto: str = "http",
        verify_ssl: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            ip=ip,
            username=username,
            password=password,
            timeout=timeout,
            **kwargs,
        )

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
            verify_ssl=verify_ssl,
        )

        logger.debug(
            "AxisAdapter init | ip=%s | timeout=%.1fs | proto=%s | verify_ssl=%s",
            ip,
            timeout,
            preferred_proto,
            verify_ssl,
        )

    # ------------------------------------------------------------------ probe

    async def probe_async(self) -> ProbeResult:
        logger.info(
            "axis probe → start | ip=%s | creds=%s",
            self.ip,
            bool(self.username or self.password),
        )

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as session:

                tasks = {
                    "serial": self.client.get_serial(session),
                    "model": self.client.get_model(session),
                    "mac": self.client.get_mac(session),
                    # "network": self.client.get_network(),
                    # "ntp": self.client.get_ntp(),
                }

                results = await asyncio.gather(
                    *tasks.values(),
                    return_exceptions=True,
                )

            data = dict(zip(tasks.keys(), results))
            errors: list[str] = []

            def pick(key: str):
                val = data.get(key)
                if isinstance(val, Exception):
                    errors.append(f"{key}: {type(val).__name__}")
                    return None
                return val

            serial = pick("serial")
            model = pick("model")
            mac = pick("mac")
            net_raw = pick("network")
            ntp_raw = pick("ntp")

            # ─── network ───
            network: Optional[NetworkInfo] = None
            if isinstance(net_raw, dict):
                network = NetworkInfo(
                    ip=net_raw.get("ip"),
                    mask=net_raw.get("mask"),
                    cidr=net_raw.get("cidr"),
                    gateway=net_raw.get("gateway"),
                    gateway_in_subnet=net_raw.get("gateway_in_subnet"),
                )

            # ─── ntp ───
            ntp: Optional[NtpInfo] = None
            if isinstance(ntp_raw, dict):
                ntp = NtpInfo(
                    enabled=bool(ntp_raw.get("enabled")),
                    server=ntp_raw.get("server"),
                    timezone=ntp_raw.get("timezone"),
                    update_period=ntp_raw.get("update_period"),
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
                network=network,
                ntp=ntp,
                confidence=confidence,
                error=", ".join(errors) if errors else None,
                raw={
                    "source": "axis_vapix",
                    "partial_errors": errors or None,
                },
            )

        except Exception as exc:
            logger.exception("axis probe → critical failure | ip=%s", self.ip)
            return ProbeResult(
                ip=self.ip,
                vendor=self.vendor,
                confidence=0.0,
                error=f"critical:{type(exc).__name__}",
                raw={
                    "source": "axis_vapix",
                    "exception": str(exc),
                },
            )
