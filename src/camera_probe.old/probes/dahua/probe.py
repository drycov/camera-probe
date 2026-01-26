from __future__ import annotations

import asyncio
import logging
from typing import ClassVar, Any, Dict

from camera_probe.probes.base import BaseProbe
from camera_probe.clients.registry import ClientRegistry
from camera_probe.models.probe_result import ProbeResult, NetworkInfo, NtpInfo
from camera_probe.probes.registry import ProbeRegistry

logger = logging.getLogger(__name__)


@ProbeRegistry.register
class DahuaProbe(BaseProbe):
    """
    Probe for Dahua cameras via CGI interface.

    Responsibilities:
    - fetch factual data only
    - tolerate partial failures
    - return ProbeResult with confidence, not decisions
    """

    vendor: ClassVar[str] = "dahua"

    def __init__(
        self,
        ip: str,
        username: str = "",
        password: str = "",
        timeout: float = 7.0,
    ) -> None:
        super().__init__(
            ip=ip,
            username=username,
            password=password,
            timeout=timeout,
        )

        client_cls = ClientRegistry.get(self.vendor)
        if not client_cls:
            raise RuntimeError(
                "Dahua client is not registered in ClientRegistry"
            )

        # ❗ probe не знает конкретный класс клиента
        self.client = client_cls(
            ip=ip,
            username=username,
            password=password,
            timeout=timeout,
        )

    async def probe_async(self) -> ProbeResult:
        logger.debug(
            "dahua probe start | ip=%s | auth=%s | timeout=%.1fs",
            self.ip,
            bool(self.username or self.password),
            self.timeout,
        )

        try:
            tasks = {
                "model": self.client.device_type(),
                "serial": self.client.serial(),
                "mac": self.client.mac(),
                "network": self.client.ip_info(),
                "ntp": self.client.ntp(),
            }

            results = await asyncio.gather(
                *tasks.values(),
                return_exceptions=True,
            )

            data: Dict[str, Any] = {}
            warnings: list[str] = []

            for key, value in zip(tasks.keys(), results):
                if isinstance(value, Exception):
                    warnings.append(f"{key}: {type(value).__name__}")
                else:
                    data[key] = value

            # ─── Network parsing (safe) ───
            network = None
            net_raw = data.get("network")
            if isinstance(net_raw, dict):
                network = NetworkInfo(
                    ip=net_raw.get("ip"),
                    mask=net_raw.get("netmask"),
                    cidr=net_raw.get("cidr"),
                    gateway=net_raw.get("gateway"),
                    gateway_in_subnet=net_raw.get("gateway_in_subnet"),
                )

            # ─── NTP parsing (safe) ───
            ntp_info = None
            ntp_raw = data.get("ntp")
            if isinstance(ntp_raw, dict):
                enabled_raw = str(ntp_raw.get("table.NTP.Enable", "")).lower()
                ntp_info = NtpInfo(
                    enabled=enabled_raw in ("true", "1", "yes"),
                    server=(ntp_raw.get("table.NTP.Address") or "").strip() or None,
                    timezone=(ntp_raw.get("table.NTP.TimeZoneDesc") or "").strip() or None,
                    update_period=(ntp_raw.get("table.NTP.UpdatePeriod") or "").strip() or None,
                )

            # ─── Confidence policy (probe-local) ───
            has_strong_id = bool(data.get("serial") or data.get("model"))
            has_identity = bool(
                data.get("serial") or data.get("model") or data.get("mac")
            )

            if has_strong_id:
                confidence = 1.0
            elif has_identity:
                confidence = 0.75
            else:
                confidence = 0.3

            result = ProbeResult(
                ip=self.ip,
                vendor=self.vendor,
                model=data.get("model"),
                serial=data.get("serial"),
                mac=data.get("mac"),
                network=network,
                ntp=ntp_info,
                confidence=confidence,
                error=None if has_identity else "no_identity_data",
                raw={
                    "source": "dahua_cgi",
                    "warnings": warnings or None,
                },
            )

            log_level = logging.INFO if has_strong_id else logging.WARNING
            logger.log(
                log_level,
                "dahua probe %s | ip=%s | serial=%s | model=%s | conf=%.2f",
                "success" if has_strong_id else "partial",
                self.ip,
                data.get("serial") or "—",
                data.get("model") or "—",
                confidence,
            )

            return result

        except Exception as exc:
            logger.exception("dahua probe critical failure | ip=%s", self.ip)
            return ProbeResult(
                ip=self.ip,
                vendor=self.vendor,
                confidence=0.0,
                error=f"critical: {type(exc).__name__}",
                raw={
                    "exception": str(exc),
                    "source": "dahua_cgi",
                },
            )
