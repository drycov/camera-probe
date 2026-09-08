from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from camera_probe.domain.models.detect_result import DetectResult
from camera_probe.domain.ports.discovery import DiscoveryPort

from camera_probe.infrastructure.discovery.budget import default_discovery_budget
from camera_probe.infrastructure.discovery.tcp import tcp_probe_ports
from camera_probe.infrastructure.discovery.rtsp import rtsp_options
from camera_probe.infrastructure.discovery.rtsp_describe import rtsp_describe
from camera_probe.infrastructure.discovery.http import http_auth_fingerprint
from camera_probe.infrastructure.discovery.onvif import onvif_probe
from camera_probe.infrastructure.discovery.onvif_device import (
    onvif_get_device_information,
    onvif_https_unicast_probe,
    onvif_unicast_probe,
)
from camera_probe.infrastructure.fingerprints.registry import FingerprintRegistry
from camera_probe.infrastructure.sdp.parse_sdp import aggregate_rtsp_vendor_markers

logger = logging.getLogger(__name__)

RTSP_PORTS = (554, 8554, 10554)
HTTP_PORTS = (80, 81, 8080, 8000, 8888, 443)
ONVIF_PORTS = (80, 8080, 8000, 443)


class DiscoveryEngine(DiscoveryPort):
    """Bounded camera discovery with process-wide protocol budgets."""

    CONFIDENCE_MAP = {"rtsp_sdp": 0.95, "http_api": 0.90, "rtsp_server": 0.70, "http_server": 0.45}

    def __init__(self, *, max_rtsp_ports: int = 1, enable_rtsp_describe: bool = True, enable_onvif_fallback: bool = True) -> None:
        self._fingerprints = FingerprintRegistry()
        self._stats: Dict[str, int] = {}
        self._stats_lock = threading.Lock()
        self._max_rtsp_ports = max(1, min(max_rtsp_ports, len(RTSP_PORTS)))
        self._enable_rtsp_describe = enable_rtsp_describe
        self._enable_onvif_fallback = enable_onvif_fallback

    async def detect(self, *, ip: str, username: str | None = None, password: str | None = None, timeout_per_port: float = 1.5, max_total_timeout: float = 10.0) -> DetectResult:
        started = datetime.now(timezone.utc)
        timeout_per_port = max(0.05, timeout_per_port)
        max_total_timeout = max(0.1, max_total_timeout)
        try:
            async with default_discovery_budget.slot("total"):
                return await asyncio.wait_for(self._detect_internal(ip=ip, username=username, password=password, timeout_per_port=timeout_per_port), timeout=max_total_timeout)
        except asyncio.TimeoutError:
            logger.warning("Discovery timeout for %s", ip)
            return DetectResult(ip=ip, vendor=None, confidence=0.0, status="timeout", evidence={"error": "timeout"})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Discovery error for %s", ip)
            return DetectResult(ip=ip, vendor=None, confidence=0.0, status="error", evidence={"error": str(exc)})
        finally:
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            logger.debug("Discovery for %s completed in %.2fs", ip, elapsed)

    async def _detect_internal(self, *, ip: str, username: str | None, password: str | None, timeout_per_port: float) -> DetectResult:
        evidence: Dict[str, object] = {}
        async with default_discovery_budget.slot("tcp"):
            open_ports: Set[int] = set(await tcp_probe_ports(ip, ports=set(RTSP_PORTS) | set(HTTP_PORTS), timeout=timeout_per_port))
        if not open_ports:
            return DetectResult(ip=ip, vendor=None, confidence=0.0, status="no_services")

        tasks: list[asyncio.Task[object]] = []
        rtsp_ports = [p for p in RTSP_PORTS if p in open_ports][: self._max_rtsp_ports]
        for port in rtsp_ports:
            tasks.append(asyncio.create_task(self._probe_rtsp_options(ip, port, evidence, timeout_per_port)))
        http_ports = [p for p in HTTP_PORTS if p in open_ports]
        if http_ports:
            tasks.append(asyncio.create_task(self._probe_http(ip, http_ports, evidence, timeout_per_port)))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        fp = self._fingerprints.match(evidence)
        if fp:
            vendor = fp.vendor(); self._update_stats(vendor)
            return DetectResult(ip=ip, vendor=vendor, confidence=fp.confidence(), method="fingerprint", evidence=evidence, status="ok")
        heuristic = self._heuristic_vendor_scoring(evidence)
        if heuristic and heuristic[1] >= 0.85:
            vendor, confidence, path = heuristic; self._update_stats(vendor)
            return DetectResult(ip=ip, vendor=vendor, confidence=confidence, method="heuristic", evidence={**evidence, "heuristic_path": path}, status="ok")

        fallback_tasks: list[asyncio.Task[object]] = []
        if self._enable_rtsp_describe and rtsp_ports:
            fallback_tasks.append(asyncio.create_task(self._probe_rtsp_describe(ip, rtsp_ports[0], username, password, timeout_per_port)))
        fallback_onvif_ports = [p for p in ONVIF_PORTS if p in open_ports]
        if self._enable_onvif_fallback and fallback_onvif_ports:
            fallback_tasks.append(asyncio.create_task(self._probe_onvif(ip, fallback_onvif_ports, username=username, password=password, timeout=timeout_per_port)))
        if fallback_tasks:
            results = await asyncio.gather(*fallback_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, dict): evidence.update(result)

        parsed = evidence.get("rtsp_sdp_parsed")
        if parsed:
            markers = aggregate_rtsp_vendor_markers(parsed)
            if markers: evidence["rtsp_vendor_markers"] = markers
        fp = self._fingerprints.match(evidence)
        if fp:
            vendor = fp.vendor(); self._update_stats(vendor)
            return DetectResult(ip=ip, vendor=vendor, confidence=fp.confidence(), method="fingerprint", evidence=evidence, status="ok")
        heuristic = self._heuristic_vendor_scoring(evidence)
        if heuristic:
            vendor, confidence, path = heuristic; self._update_stats(vendor)
            return DetectResult(ip=ip, vendor=vendor, confidence=confidence, method="heuristic", evidence={**evidence, "heuristic_path": path}, status="ok")
        return DetectResult(ip=ip, vendor=None, confidence=0.0, evidence=evidence or None, status="unknown")

    async def _probe_rtsp_options(self, ip: str, port: int, evidence: Dict[str, object], timeout: float) -> None:
        try:
            async with default_discovery_budget.slot("rtsp"):
                server = await rtsp_options(ip, port, timeout=timeout)
            if server: evidence["rtsp_server"] = server; evidence["rtsp_port"] = str(port)
        except asyncio.CancelledError: raise
        except Exception as exc: logger.debug("RTSP OPTIONS failed | ip=%s port=%s | error=%s", ip, port, type(exc).__name__)

    async def _probe_rtsp_describe(self, ip: str, port: int, username: str | None, password: str | None, timeout: float) -> Dict[str, object]:
        try:
            async with default_discovery_budget.slot("rtsp"):
                return await rtsp_describe(ip=ip, port=port, username=username, password=password, timeout=timeout)
        except asyncio.CancelledError: raise
        except Exception as exc:
            logger.debug("RTSP DESCRIBE failed | ip=%s port=%s | error=%s", ip, port, type(exc).__name__)
            return {}

    async def _probe_http(self, ip: str, ports: List[int], evidence: Dict[str, object], timeout: float) -> None:
        try:
            async with default_discovery_budget.slot("http"):
                result = await http_auth_fingerprint(ip, ports=ports, timeout=timeout)
            if result: evidence.update(result)
        except asyncio.CancelledError: raise
        except Exception as exc: logger.debug("HTTP discovery failed | ip=%s | error=%s", ip, type(exc).__name__)

    async def _probe_onvif(self, ip: str, ports: List[int], *, username: str | None, password: str | None, timeout: float) -> Dict[str, object]:
        evidence: Dict[str, object] = {}
        try:
            async with default_discovery_budget.slot("onvif"):
                multicast_ev = await asyncio.wait_for(onvif_probe(ip), timeout=timeout)
                if multicast_ev: evidence.update(multicast_ev)
                xaddrs = _collect_onvif_xaddrs(multicast_ev or {})
                if not xaddrs:
                    unicast, https_unicast = await asyncio.gather(onvif_unicast_probe(ip, ports), onvif_https_unicast_probe(ip, ports, timeout=timeout), return_exceptions=True)
                    if isinstance(unicast, list): xaddrs.extend(unicast)
                    if isinstance(https_unicast, list): xaddrs.extend(https_unicast)
                xaddrs = _dedupe_preserve_order(xaddrs)
                if xaddrs:
                    evidence["onvif_xaddrs"] = " ".join(xaddrs); evidence["onvif_xaddr"] = xaddrs[0]
                for xaddr in xaddrs[:1]:
                    device_info = await onvif_get_device_information(xaddr, username=username, password=password, timeout=timeout)
                    if device_info:
                        evidence.update(device_info); evidence["onvif_device_info_xaddr"] = xaddr; break
        except asyncio.CancelledError: raise
        except Exception as exc: logger.debug("ONVIF fallback failed | ip=%s | error=%s", ip, type(exc).__name__)
        return evidence

    def _heuristic_vendor_scoring(self, evidence: Dict[str, object]) -> Optional[tuple[str, float, str]]:
        scores: Dict[str, float] = {}; path: List[str] = []
        def add(vendor: str, score: float, reason: str) -> None:
            scores[vendor] = max(scores.get(vendor, 0.0), score); path.append(f"{vendor}:{score:.2f}<-{reason}")
        markers = evidence.get("rtsp_vendor_markers"); markers = [markers] if isinstance(markers, str) else markers
        if isinstance(markers, list):
            m = {str(x).lower() for x in markers}
            for v in ("dahua", "hikvision", "axis", "xiongmai", "uniview"):
                if v in m: add(v.capitalize(), self.CONFIDENCE_MAP["rtsp_sdp"], "RTSP SDP")
        http_markers = evidence.get("http_vendor_markers"); http_markers = [http_markers] if isinstance(http_markers, str) else http_markers
        if isinstance(http_markers, list):
            m = {str(x).lower() for x in http_markers}
            for v in ("dahua", "hikvision", "uniview", "xiongmai"):
                if v in m: add(v.capitalize(), self.CONFIDENCE_MAP["http_api"], "HTTP API")
        srv = evidence.get("rtsp_server")
        if isinstance(srv, str):
            s = srv.lower()
            for v in ("dahua", "hikvision", "axis"):
                if v in s: add(v.capitalize(), self.CONFIDENCE_MAP["rtsp_server"], "RTSP Server")
        http_srv = evidence.get("http_server")
        if isinstance(http_srv, str):
            s = http_srv.lower()
            for v in ("dahua", "hikvision", "axis"):
                if v in s: add(v.capitalize(), self.CONFIDENCE_MAP["http_server"], "HTTP Server")
        onvif_vendor = _vendor_from_onvif(evidence)
        if onvif_vendor: add(onvif_vendor, 0.85, "ONVIF")
        if not scores: return None
        vendor, confidence = max(scores.items(), key=lambda item: item[1])
        return vendor, confidence, " | ".join(path)

    def _update_stats(self, vendor: str) -> None:
        with self._stats_lock:
            self._stats[vendor] = self._stats.get(vendor, 0) + 1; self._stats["total"] = self._stats.get("total", 0) + 1

    def get_stats(self) -> Dict[str, int]:
        with self._stats_lock: return dict(self._stats)


def _collect_onvif_xaddrs(evidence: Dict[str, object]) -> list[str]:
    value = evidence.get("onvif_xaddrs")
    if isinstance(value, str) and value.strip(): return [item.strip() for item in value.split() if item.strip()]
    value = evidence.get("onvif_xaddr")
    if isinstance(value, str) and value.strip(): return [value.strip()]
    return []


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    result: list[str] = []; seen: set[str] = set()
    for value in values:
        if value not in seen: seen.add(value); result.append(value)
    return result


def _vendor_from_onvif(evidence: Dict[str, object]) -> str | None:
    manufacturer = evidence.get("onvif_manufacturer"); model = evidence.get("onvif_model")
    manufacturer_text = manufacturer.lower() if isinstance(manufacturer, str) else ""; model_text = model.lower() if isinstance(model, str) else ""
    if "hikvision" in manufacturer_text or "ds-" in model_text: return "Hikvision"
    if "dahua" in manufacturer_text or "dh-" in model_text or "ipc-h" in model_text: return "Dahua"
    if "axis" in manufacturer_text: return "Axis"
    if "uniview" in manufacturer_text or "unv" in manufacturer_text: return "Uniview"
    if "xiongmai" in manufacturer_text or "xm" in model_text: return "Xiongmai"
    return None
