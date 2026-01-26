from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set

from camera_probe.domain.models.detect_result import DetectResult
from camera_probe.domain.ports.discovery import DiscoveryPort

from camera_probe.infrastructure.discovery.tcp import tcp_probe_ports
from camera_probe.infrastructure.discovery.rtsp import rtsp_options
from camera_probe.infrastructure.discovery.rtsp_describe import rtsp_describe
from camera_probe.infrastructure.discovery.http import http_auth_fingerprint

from camera_probe.infrastructure.discovery.onvif import onvif_probe
from camera_probe.infrastructure.discovery.onvif_device import (
    onvif_unicast_probe,
    onvif_https_unicast_probe,
    onvif_https_auth_probe,
    onvif_get_device_information,
)

from camera_probe.infrastructure.fingerprints.registry import FingerprintRegistry
from camera_probe.infrastructure.sdp.parse_sdp import aggregate_rtsp_vendor_markers

logger = logging.getLogger(__name__)

RTSP_PORTS = (554, 8554, 10554)
HTTP_PORTS = (80, 81, 8080, 8000, 8888, 443)
ONVIF_PORTS = (80, 8080, 8000, 443)


class DiscoveryEngine(DiscoveryPort):
    """
    Production-grade vendor discovery engine.
    Vendor detection is based ONLY on RTSP and HTTP signals.
    ONVIF is explicitly excluded from vendor detection.
    """

    # ────────────────────────────────────────────────
    # Confidence weights (single source of truth)
    # ────────────────────────────────────────────────
    CONFIDENCE_MAP = {
        "rtsp_sdp": 0.95,
        "http_api": 0.90,
        "rtsp_server": 0.70,
        "http_server": 0.45,
    }

    def __init__(self) -> None:
        self._fingerprints = FingerprintRegistry()
        self._stats: Dict[str, int] = {}

    # ────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────
    async def detect(
        self,
        *,
        ip: str,
        username: str | None = None,
        password: str | None = None,
        timeout_per_port: float = 1.5,
        max_total_timeout: float = 10.0,
    ) -> DetectResult:

        started = datetime.now()
        logger.debug("Discovery started for %s", ip)

        try:
            return await asyncio.wait_for(
                self._detect_internal(
                    ip=ip,
                    username=username,
                    password=password,
                    timeout_per_port=timeout_per_port,
                ),
                timeout=max_total_timeout,
            )

        except asyncio.TimeoutError:
            logger.warning("Discovery timeout for %s", ip)
            return DetectResult(
                ip=ip,
                vendor=None,
                confidence=0.0,
                status="timeout",
                evidence={"error": "timeout"},
            )

        except Exception as e:
            logger.exception("Discovery error for %s", ip)
            return DetectResult(
                ip=ip,
                vendor=None,
                confidence=0.0,
                status="error",
                evidence={"error": str(e)},
            )

        finally:
            elapsed = (datetime.now() - started).total_seconds()
            logger.debug("Discovery for %s completed in %.2fs", ip, elapsed)

    # ────────────────────────────────────────────────
    # Internal pipeline
    # ────────────────────────────────────────────────
    async def _detect_internal(
        self,
        *,
        ip: str,
        username: str | None,
        password: str | None,
        timeout_per_port: float,
    ) -> DetectResult:

        evidence: Dict[str, object] = {}
        open_ports: Set[int] = set()

        # ────────────────────────────────────────────────
        # 1. TCP port scan
        # ────────────────────────────────────────────────
        open_ports = await tcp_probe_ports(
            ip,
            ports=set(RTSP_PORTS) | set(HTTP_PORTS),
            timeout=timeout_per_port,
        )

        if not open_ports:
            return DetectResult(
                ip=ip,
                vendor=None,
                confidence=0.0,
                status="no_services",
            )

        logger.debug("Open ports for %s: %s", ip, sorted(open_ports))

        # ────────────────────────────────────────────────
        # 2. Parallel protocol probes
        # ────────────────────────────────────────────────
        tasks = []

        for port in RTSP_PORTS:
            if port in open_ports:
                tasks.append(self._probe_rtsp_options(ip, port, evidence))

        http_ports = [p for p in open_ports if p in HTTP_PORTS]
        if http_ports:
            tasks.append(self._probe_http(ip, http_ports, evidence))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # ────────────────────────────────────────────────
        # 3. RTSP DESCRIBE (SDP)
        # ────────────────────────────────────────────────
        if any(p in open_ports for p in RTSP_PORTS):
            for port in RTSP_PORTS:
                if port not in open_ports:
                    continue

                sdp = await rtsp_describe(
                    ip=ip,
                    port=port,
                    username=username,
                    password=password,
                    timeout=timeout_per_port,
                )

                if not sdp:
                    continue

                evidence.update(sdp)
                evidence["rtsp_port"] = str(port)

                parsed = sdp.get("rtsp_sdp_parsed")
                if parsed:
                    markers = aggregate_rtsp_vendor_markers(parsed)
                    if markers:
                        evidence["rtsp_vendor_markers"] = markers

                break

        logger.debug("Collected evidence for %s: %s", ip, list(evidence.keys()))

        # ────────────────────────────────────────────────
        # 4. Fingerprint matching (absolute priority)
        # ────────────────────────────────────────────────
        fp = self._fingerprints.match(evidence)
        if fp:
            vendor = fp.vendor()
            confidence = fp.confidence()
            self._update_stats(vendor)

            logger.info(
                "Vendor detected (fingerprint): %s confidence=%.2f",
                vendor,
                confidence,
            )

            return DetectResult(
                ip=ip,
                vendor=vendor,
                confidence=confidence,
                method="fingerprint",
                evidence=evidence,
                status="ok",
            )

        # ────────────────────────────────────────────────
        # 5. Heuristic scoring
        # ────────────────────────────────────────────────
        heuristic = self._heuristic_vendor_scoring(evidence)
        if heuristic:
            vendor, confidence, path = heuristic
            self._update_stats(vendor)

            logger.info(
                "Vendor detected (heuristic): %s confidence=%.2f path=%s",
                vendor,
                confidence,
                path,
            )

            return DetectResult(
                ip=ip,
                vendor=vendor,
                confidence=confidence,
                method="heuristic",
                evidence=evidence,
                status="ok",
            )

        # ────────────────────────────────────────────────
        # 6. Fallback
        # ────────────────────────────────────────────────
        return DetectResult(
            ip=ip,
            vendor=None,
            confidence=0.0,
            evidence=evidence or None,
            status="unknown",
        )

    # ────────────────────────────────────────────────
    # Protocol probes
    # ────────────────────────────────────────────────
    async def _probe_rtsp_options(self, ip: str, port: int, evidence: Dict) -> None:
        try:
            server = await rtsp_options(ip, port)
            if server:
                evidence["rtsp_server"] = server
        except Exception:
            pass

    async def _probe_http(self, ip: str, ports: List[int], evidence: Dict) -> None:
        try:
            http_ev = await http_auth_fingerprint(ip, ports=ports)
            if http_ev:
                evidence.update(http_ev)
        except Exception:
            pass

    # ────────────────────────────────────────────────
    # Heuristic scoring engine
    # ────────────────────────────────────────────────
    def _heuristic_vendor_scoring(
        self, evidence: Dict[str, object]
    ) -> Optional[tuple[str, float, str]]:

        scores: Dict[str, float] = {}
        path: List[str] = []

        def add(vendor: str, score: float, reason: str) -> None:
            scores[vendor] = max(scores.get(vendor, 0.0), score)
            path.append(f"{vendor}:{score:.2f}←{reason}")

        # RTSP SDP
        markers = evidence.get("rtsp_vendor_markers")
        if isinstance(markers, list):
            m = set(x.lower() for x in markers)
            for v in ("dahua", "hikvision", "axis", "xiongmai", "uniview"):
                if v in m:
                    add(v.capitalize(), self.CONFIDENCE_MAP["rtsp_sdp"], "RTSP SDP")

        # HTTP API
        http_markers = evidence.get("http_vendor_markers")
        if isinstance(http_markers, list):
            m = set(x.lower() for x in http_markers)
            for v in ("dahua", "hikvision", "uniview", "xiongmai"):
                if v in m:
                    add(v.capitalize(), self.CONFIDENCE_MAP["http_api"], "HTTP API")

        # RTSP Server
        srv = evidence.get("rtsp_server")
        if isinstance(srv, str):
            s = srv.lower()
            for v in ("dahua", "hikvision", "axis"):
                if v in s:
                    add(v.capitalize(), self.CONFIDENCE_MAP["rtsp_server"], "RTSP Server")

        # HTTP Server
        http_srv = evidence.get("http_server")
        if isinstance(http_srv, str):
            s = http_srv.lower()
            for v in ("dahua", "hikvision", "axis"):
                if v in s:
                    add(v.capitalize(), self.CONFIDENCE_MAP["http_server"], "HTTP Server")

        if not scores:
            return None

        vendor, confidence = max(scores.items(), key=lambda x: x[1])
        return vendor, confidence, " | ".join(path)

    # ────────────────────────────────────────────────
    # Stats
    # ────────────────────────────────────────────────
    def _update_stats(self, vendor: str) -> None:
        self._stats[vendor] = self._stats.get(vendor, 0) + 1
        self._stats["total"] = self._stats.get("total", 0) + 1

    def get_stats(self) -> Dict[str, int]:
        return dict(self._stats)
