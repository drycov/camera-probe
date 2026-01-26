from __future__ import annotations

import asyncio
import logging
from typing import ClassVar, Any, Dict

import aiohttp

from camera_probe.probes.base import BaseProbe
from camera_probe.clients.registry import ClientRegistry
from camera_probe.models.probe_result import ProbeResult
from camera_probe.probes.registry import ProbeRegistry

logger = logging.getLogger(__name__)


@ProbeRegistry.register
class AxisProbe(BaseProbe):
    """
    Probe for Axis cameras via VAPIX API.

    Responsibilities:
    - collect factual data only
    - tolerate partial failures
    - return ProbeResult with confidence, not decisions
    """

    vendor: ClassVar[str] = "axis"

    def __init__(
        self,
        ip: str,
        username: str = "",
        password: str = "",
        timeout: float = 6.0,
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
                "Axis client is not registered in ClientRegistry"
            )

        # probe не знает конкретную реализацию клиента
        self.client = client_cls(
            ip=ip,
            username=username,
            password=password,
            timeout=timeout,
        )

    async def probe_async(self) -> ProbeResult:
        logger.debug(
            "axis probe start | ip=%s | auth=%s | timeout=%.1fs",
            self.ip,
            bool(self.username or self.password),
            self.timeout,
        )

        timeout_cfg = aiohttp.ClientTimeout(total=self.timeout)
        auth = (
            aiohttp.BasicAuth(self.username, self.password)
            if self.username or self.password
            else None
        )

        try:
            async with aiohttp.ClientSession(
                timeout=timeout_cfg,
                auth=auth,
            ) as session:

                tasks = {
                    "serial": self.client.get_serial(session),
                    "model": self.client.get_model(session),
                    "mac": self.client.get_mac(session),
                    # future:
                    # "network": self.client.get_network_info(session),
                    # "ntp": self.client.get_ntp(session),
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

                # ─── Network / NTP (пока не реализованы) ───
                network = None
                ntp = None

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
                    ntp=ntp,
                    confidence=confidence,
                    error=None if has_identity else "no_identity_data",
                    raw={
                        "source": "axis_vapix",
                        "warnings": warnings or None,
                    },
                )

                log_level = logging.INFO if has_strong_id else logging.WARNING
                logger.log(
                    log_level,
                    "axis probe %s | ip=%s | serial=%s | model=%s | conf=%.2f",
                    "success" if has_strong_id else "partial",
                    self.ip,
                    data.get("serial") or "—",
                    data.get("model") or "—",
                    confidence,
                )

                return result

        except Exception as exc:
            logger.exception("axis probe critical failure | ip=%s", self.ip)
            return ProbeResult(
                ip=self.ip,
                vendor=self.vendor,
                confidence=0.0,
                error=f"critical: {type(exc).__name__}",
                raw={
                    "exception": str(exc),
                    "source": "axis_vapix",
                },
            )
