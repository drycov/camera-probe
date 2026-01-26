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
class DahuaAdapter(CameraAdapter):
    """
    Adapter for Dahua / IMOU / Lechange cameras via CGI interface.
    """

    vendor: Final[str] = "dahua"

    DAHUA_SIGNATURES = frozenset(
        {"DH-", "DHI-", "IPC-H", "IMOU", "LECHANGE", "DAHUA", "TIANDY"}
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
        url = f"http://{ip}/cgi-bin/magicBox.cgi?action=getDeviceType"
        evidence: Dict[str, Any] = {
            "method": "magicBox.getDeviceType",
            "url": url,
            "timeout": timeout,
        }

        logger.debug("dahua detect → start | ip=%s", ip)

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as session:
                async with session.get(url, allow_redirects=False) as resp:
                    evidence["status"] = resp.status

                    if resp.status != 200:
                        return cls._no_match(ip, evidence, f"http_{resp.status}")

                    body = await resp.text(errors="ignore")
                    upper = body.upper()
                    evidence["body_preview"] = body[:300]

                    matches = [s for s in cls.DAHUA_SIGNATURES if s in upper]
                    if not matches:
                        return cls._no_match(ip, evidence, "no_signatures")

                    confidence = min(0.97, 0.45 + len(matches) * 0.22)
                    evidence["matched"] = matches

                    logger.info(
                        "dahua detect → MATCH | ip=%s | conf=%.2f | sig=%s",
                        ip,
                        confidence,
                        matches,
                    )

                    return DetectResult(
                        ip=ip,
                        vendor=cls.vendor,
                        adapter_cls=cls,
                        confidence=confidence,
                        status="matched",
                        evidence=evidence,
                    )

        except Exception as exc:
            logger.warning("dahua detect → error | ip=%s | %s", ip, exc)
            evidence["error"] = str(exc)
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
        timeout: float = 7.0,
        prefer_https: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            ip=ip,
            username=username,
            password=password,
            timeout=timeout,
            **kwargs,
        )

        self.prefer_https: Final[bool] = prefer_https

        client_cls = ClientRegistry.get(self.vendor)
        if client_cls is None:
            raise RuntimeError(f"No client registered for vendor '{self.vendor}'")

        # DahuaCgiClient поддерживает prefer_https -> оставляем
        self.client = client_cls(
            ip=ip,
            username=username,
            password=password,
            timeout=timeout,
            prefer_https=prefer_https,
        )

        logger.debug(
            "DahuaAdapter init | ip=%s | timeout=%.1fs | prefer_https=%s",
            ip,
            timeout,
            prefer_https,
        )

    # ------------------------------------------------------------------ probe

    async def probe_async(self) -> ProbeResult:
        logger.info(
            "dahua probe → start | ip=%s | creds=%s | https=%s",
            self.ip,
            bool(self.username or self.password),
            self.prefer_https,
        )

        try:
            tasks = {
                "vendor":   self.client.get_vendor(),
                "model":    self.client.get_device_type(),
                "serial":   self.client.get_serial(),
                "firmware": self.client.get_firmware(),
                "mac":      self.client.get_mac(),
                "network":  self.client.get_network_info(),
                "ntp":      self.client.get_ntp_info(),
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

            vendor_raw = pick("vendor")
            model = pick("model")
            serial = pick("serial")
            firmware = pick("firmware")
            mac = pick("mac")
            net_raw = pick("network")
            ntp_raw = pick("ntp")

            # ─── vendor normalization ───
            # Источник истины — адаптер; vendor клиента используем только как доп. сигнал.
            vendor = self.vendor
            if isinstance(vendor_raw, str) and vendor_raw.strip():
                vendor = vendor_raw.strip().lower()

            # ─── network ───
            network: Optional[NetworkInfo] = None
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
                    enabled=str(ntp_raw.get("table.NTP.Enable", "")).lower()
                    in {"1", "true", "yes"},
                    server=ntp_raw.get("table.NTP.Address") or None,
                    timezone=ntp_raw.get("table.NTP.TimeZoneDesc") or None,
                    update_period=(
                        int(ntp_raw["table.NTP.UpdatePeriod"])
                        if ntp_raw.get("table.NTP.UpdatePeriod")
                        else None
                    ),
                )

            identity_ok = bool(serial or model or mac)
            confidence = (
                1.0   if serial and model
                else 0.9 if serial
                else 0.8 if model and mac
                else 0.7 if model or mac
                else 0.4
            )

            logger.log(
                logging.INFO if identity_ok else logging.WARNING,
                "dahua probe → %s | ip=%s | serial=%s | model=%s | conf=%.2f",
                "success" if identity_ok else "partial/weak",
                self.ip,
                serial or "—",
                model or "—",
                confidence,
            )

            return ProbeResult(
                ip=self.ip,
                vendor=vendor,
                model=model,
                serial=serial,
                mac=mac,
                firmware=firmware,
                network=network,
                ntp=ntp,
                confidence=confidence,
                error=", ".join(errors) if errors else None,
                raw={
                    "source": "dahua_cgi",
                    "partial_errors": errors or None,
                },
            )

        except Exception as exc:
            logger.exception("dahua probe → critical failure | ip=%s", self.ip)
            return ProbeResult(
                ip=self.ip,
                vendor=self.vendor,
                confidence=0.0,
                error=f"critical:{type(exc).__name__}",
                raw={
                    "source": "dahua_cgi",
                    "exception": str(exc),
                },
            )
