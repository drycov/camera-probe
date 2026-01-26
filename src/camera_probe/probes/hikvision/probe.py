from __future__ import annotations

import asyncio
import logging
from typing import ClassVar, Final, Any, Dict

from camera_probe.probes.base import BaseProbe
from camera_probe.clients.registry import ClientRegistry
from camera_probe.models.probe_result import ProbeResult, NetworkInfo
from camera_probe.probes.registry import ProbeRegistry

logger = logging.getLogger(__name__)


@ProbeRegistry.register
class HikvisionProbe(BaseProbe):
    """
    Probe for Hikvision cameras via ISAPI.

    Responsibilities:
    - fetch factual data only
    - no heuristics outside confidence calculation
    - no fallback logic
    """

    vendor: ClassVar[str] = "hikvision"

    def __init__(
        self,
        ip: str,
        username: str = "",
        password: str = "",
        timeout: float = 6.0,
        try_anonymous: bool = True,
    ) -> None:
        super().__init__(
            ip=ip,
            username=username,
            password=password,
            timeout=timeout,
        )

        self.try_anonymous: Final[bool] = try_anonymous

        client_cls = ClientRegistry.get(self.vendor)
        if not client_cls:
            raise RuntimeError(
                "Hikvision client is not registered in ClientRegistry"
            )

        # ❗ probe не знает конкретный класс клиента
        self.client = client_cls(
            ip=ip,
            username=username,
            password=password,
            timeout=timeout,
            try_anonymous=try_anonymous,
        )

    async def probe_async(self) -> ProbeResult:
        logger.debug(
            "hikvision probe start | ip=%s | auth=%s",
            self.ip,
            bool(self.username or self.password),
        )

        try:
            tasks = {
                "serial": self.client.get_serial(),
                "model": self.client.get_model(),
                "mac": self.client.get_mac(),
                "firmware": self.client.get_software_version(),
                "network": self.client.get_network_info(),
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

            # ─── Confidence policy (probe-local) ───
            has_serial = bool(data.get("serial"))
            has_identity = bool(
                data.get("serial") or data.get("model") or data.get("mac")
            )

            if has_serial:
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
                firmware=data.get("firmware"),
                network=network,
                ntp=None,  # NTP not collected yet
                confidence=confidence,
                error=None if has_identity else "no_identity_data",
                raw={
                    "source": "hikvision_isapi",
                    "warnings": warnings or None,
                },
            )

            log_level = logging.INFO if has_serial else logging.WARNING
            logger.log(
                log_level,
                "hikvision probe %s | ip=%s | serial=%s | model=%s | conf=%.2f",
                "success" if has_serial else "partial",
                self.ip,
                data.get("serial") or "—",
                data.get("model") or "—",
                confidence,
            )

            return result

        except Exception as exc:
            logger.exception("hikvision probe critical failure | ip=%s", self.ip)
            return ProbeResult(
                ip=self.ip,
                vendor=self.vendor,
                confidence=0.0,
                error=f"critical: {type(exc).__name__}",
                raw={
                    "exception": str(exc),
                    "source": "hikvision_isapi",
                },
            )
