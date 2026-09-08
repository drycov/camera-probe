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
from camera_probe.infrastructure.discovery.onvif_device import onvif_get_device_information, onvif_https_unicast_probe, onvif_unicast_probe
from camera_probe.infrastructure.fingerprints.registry import FingerprintRegistry
from camera_probe.infrastructure.sdp.parse_sdp import aggregate_rtsp_vendor_markers

logger = logging.getLogger(__name__)
RTSP_PORTS = (554, 8554, 10554)
HTTP_PORTS = (80, 81, 8080, 8000, 8888, 443)
ONVIF_PORTS = (80, 8080, 8000, 443)

class DiscoveryEngine(DiscoveryPort):
    """Bounded discovery with process-wide resource arbitration."""
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
            return DetectResult(ip=ip, vendor=None, confidence=0.0, status="timeout", evidence={"error": "timeout"})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Discovery error for %s", ip)
            return DetectResult(ip=ip, vendor=None, confidence=0.0, status="error", evidence={"error": str(exc)})
        finally:
            logger.debug("Discovery for %s completed in %.2fs", ip, (datetime.now(timezone.utc) - started).total_seconds())

    async def _detect_internal(self, *, ip: str, username: str | None, password: str | None, timeout_per_port: float) -> DetectResult:
        evidence: Dict[str, object] = {}
        open_ports: Set[int] = set(await tcp_probe_ports(ip, ports=set(RTSP_PORTS) | set(HTTP_PORTS), timeout=timeout_per_port))
        if not open_ports:
            return DetectResult(ip=ip, vendor=None, confidence=0.0, status="no_services")
        tasks: list[asyncio.Task[object]] = []
        rtsp_ports = [p for p in RTSP_PORTS if p in open_ports][:self._max_rtsp_ports]
        for port in rtsp_ports:
            tasks.append(asyncio.create_task(self._probe_rtsp_options(ip, port, evidence, timeout_per_port)))
        http_ports = [p for p in HTTP_PORTS if p in open_ports]
        if http_ports:
            tasks.append(asyncio.create_task(self._probe_http(ip, http_ports, evidence, timeout_per_port)))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        result = self._result_from_evidence(ip, evidence)
        if result:
            return result

        fallback: list[asyncio.Task[object]] = []
        if self._enable_rtsp_describe and rtsp_ports:
            fallback.append(asyncio.create_task(self._probe_rtsp_describe(ip, rtsp_ports[0], username, password, timeout_per_port)))
        fallback_ports = [p for p in ONVIF_PORTS if p in open_ports]
        if self._enable_onvif_fallback and fallback_ports:
            fallback.append(asyncio.create_task(self._probe_onvif(ip, fallback_ports, username=username, password=password, timeout=timeout_per_port)))
        if fallback:
            for item in await asyncio.gather(*fallback, return_exceptions=True):
                if isinstance(item, dict): evidence.update(item)
        parsed = evidence.get("rtsp_sdp_parsed")
        if parsed:
            markers = aggregate_rtsp_vendor_markers(parsed)
            if markers: evidence["rtsp_vendor_markers"] = markers
        return self._result_from_evidence(ip, evidence) or DetectResult(ip=ip, vendor=None, confidence=0.0, evidence=evidence or None, status="unknown")

    def _result_from_evidence(self, ip: str, evidence: Dict[str, object]) -> DetectResult | None:
        fp = self._fingerprints.match(evidence)
        if fp:
            vendor = fp.vendor(); self._update_stats(vendor)
            return DetectResult(ip=ip, vendor=vendor, confidence=fp.confidence(), method="fingerprint", evidence=evidence, status="ok")
        heuristic = self._heuristic_vendor_scoring(evidence)
        if heuristic and (heuristic[1] >= 0.85 or evidence.get("rtsp_sdp_parsed") is not None):
            vendor, confidence, path = heuristic; self._update_stats(vendor)
            return DetectResult(ip=ip, vendor=vendor, confidence=confidence, method="heuristic", evidence={**evidence, "heuristic_path": path}, status="ok")
        return None

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
        except Exception as exc: logger.debug("RTSP DESCRIBE failed | ip=%s port=%s | error=%s", ip, port, type(exc).__name__); return {}

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
                multicast = await asyncio.wait_for(onvif_probe(ip), timeout=timeout)
                if multicast: evidence.update(multicast)
                xaddrs = _collect_onvif_xaddrs(multicast or {})
                if not xaddrs:
                    unicast, https = await asyncio.gather(onvif_unicast_probe(ip, ports), onvif_https_unicast_probe(ip, ports, timeout=timeout), return_exceptions=True)
                    if isinstance(unicast, list): xaddrs.extend(unicast)
                    if isinstance(https, list): xaddrs.extend(https)
                xaddrs = _dedupe_preserve_order(xaddrs)
                if xaddrs:
                    evidence["onvif_xaddrs"] = " ".join(xaddrs); evidence["onvif_xaddr"] = xaddrs[0]
                if xaddrs:
                    info = await onvif_get_device_information(xaddrs[0], username=username, password=password, timeout=timeout)
                    if info: evidence.update(info); evidence["onvif_device_info_xaddr"] = xaddrs[0]
        except asyncio.CancelledError: raise
        except Exception as exc: logger.debug("ONVIF fallback failed | ip=%s | error=%s", ip, type(exc).__name__)
        return evidence

    def _heuristic_vendor_scoring(self, evidence: Dict[str, object]) -> Optional[tuple[str, float, str]]:
        scores: Dict[str, float] = {}; path: List[str] = []
        def add(vendor: str, score: float, reason: str) -> None: scores[vendor] = max(scores.get(vendor, 0.0), score); path.append(f"{vendor}:{score:.2f}<-{reason}")
        markers = evidence.get("rtsp_vendor_markers"); markers = [markers] if isinstance(markers, str) else markers
        if isinstance(markers, list):
            m = {str(x).lower() for x in markers}
            for v in ("dahua", "hikvision", "axis", "xiongmai", "uniview"):
                if v in m: add(v.capitalize(), .95, "RTSP SDP")
        http_markers = evidence.get("http_vendor_markers"); http_markers = [http_markers] if isinstance(http_markers, str) else http_markers
        if isinstance(http_markers, list):
            m = {str(x).lower() for x in http_markers}
            for v in ("dahua", "hikvision", "uniview", "xiongmai"):
                if v in m: add(v.capitalize(), .90, "HTTP API")
        for key, score, reason, vendors in (("rtsp_server", .70, "RTSP Server", ("dahua", "hikvision", "axis")), ("http_server", .45, "HTTP Server", ("dahua", "hikvision", "axis"))):
            value = evidence.get(key)
            if isinstance(value, str):
                text = value.lower()
                for v in vendors:
                    if v in text: add(v.capitalize(), score, reason)
        vendor = _vendor_from_onvif(evidence)
        if vendor: add(vendor, .85, "ONVIF")
        if not scores: return None
        selected, confidence = max(scores.items(), key=lambda item: item[1])
        return selected, confidence, " | ".join(path)

    def _update_stats(self, vendor: str) -> None:
        with self._stats_lock:
            self._stats[vendor] = self._stats.get(vendor, 0) + 1; self._stats["total"] = self._stats.get("total", 0) + 1

    def get_stats(self) -> Dict[str, int]:
        with self._stats_lock: return dict(self._stats)


def _collect_onvif_xaddrs(evidence: Dict[str, object]) -> list[str]:
    value = evidence.get("onvif_xaddrs")
    if isinstance(value, str) and value.strip(): return [x.strip() for x in value.split() if x.strip()]
    value = evidence.get("onvif_xaddr")
    return [value.strip()] if isinstance(value, str) and value.strip() else []

def _dedupe_preserve_order(values: list[str]) -> list[str]:
    result: list[str] = []; seen: set[str] = set()
    for value in values:
        if value not in seen: seen.add(value); result.append(value)
    return result

def _vendor_from_onvif(evidence: Dict[str, object]) -> str | None:
    manufacturer = evidence.get("onvif_manufacturer"); model = evidence.get("onvif_model")
    m = manufacturer.lower() if isinstance(manufacturer, str) else ""; model_text = model.lower() if isinstance(model, str) else ""
    if "hikvision" in m or "ds-" in model_text: return "Hikvision"
    if "dahua" in m or "dh-" in model_text or "ipc-h" in model_text: return "Dahua"
    if "axis" in m: return "Axis"
    if "uniview" in m or "unv" in m: return "Uniview"
    if "xiongmai" in m or "xm" in model_text: return "Xiongmai"
    return None
