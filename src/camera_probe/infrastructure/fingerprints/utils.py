# camera_probe/infrastructure/fingerprints/utils.py
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Dict, List, Pattern


class PatternMatcher:
    """Utility class for pattern matching in evidence"""

    MODEL_NUMBER_PATTERNS = [
        re.compile(r"[A-Z]{2,4}-[A-Z0-9-]{5,15}", re.IGNORECASE),  # DS-2CD2143G0-I, DH-IPC-HFWXXXX
        re.compile(r"IPC-[A-Z0-9-]{5,15}", re.IGNORECASE),  # IPC-HDWXXXX
        re.compile(r"[A-Z]{3,4}\d{3,6}[A-Z]*", re.IGNORECASE),  # ABC123D, ABCD1234
        re.compile(r"MODEL[:=]\s*([A-Z0-9-]+)", re.IGNORECASE),  # MODEL: DS-2CD2143G0-I
    ]
    
    @staticmethod
    def contains_any(text: str, patterns: List[str], case_sensitive: bool = False) -> bool:
        """Check if text contains any of the patterns"""
        if not text:
            return False

        if not case_sensitive:
            text = text.lower()
            return any(pattern.lower() in text for pattern in patterns)

        return any(pattern in text for pattern in patterns)
    
    @staticmethod
    def matches_any(text: str, regex_patterns: List[Pattern], case_sensitive: bool = False) -> bool:
        """Check if text matches any of the regex patterns"""
        if not text:
            return False

        if case_sensitive:
            return any(pattern.search(text) for pattern in regex_patterns)

        return any(
            re.search(pattern.pattern, text, pattern.flags | re.IGNORECASE)
            for pattern in regex_patterns
        )
    
    @staticmethod
    def extract_model_number(text: str) -> str | None:
        """Extract model number from text"""
        if not text:
            return None

        for pattern in PatternMatcher.MODEL_NUMBER_PATTERNS:
            match = pattern.search(text)
            if match:
                return match.group(0)

        return None


class EvidenceView:
    """Normalized view over evidence dict for consistent matching."""

    def __init__(self, evidence: Mapping[str, object]) -> None:
        self._evidence = evidence
        self._text_cache: dict[str, str] = {}
        self._list_cache: dict[str, list[str]] = {}

    def text(self, key: str) -> str:
        if key not in self._text_cache:
            value = self._evidence.get(key)
            self._text_cache[key] = value.lower() if isinstance(value, str) else ""
        return self._text_cache[key]

    def list(self, key: str) -> list[str]:
        if key not in self._list_cache:
            value = self._evidence.get(key)
            if isinstance(value, (list, tuple, set)):
                normalized = [
                    item.lower()
                    for item in value
                    if isinstance(item, str) and item
                ]
            else:
                normalized = []
            self._list_cache[key] = normalized
        return self._list_cache[key]

    def has_marker(self, key: str, marker: str) -> bool:
        return marker in self.list(key)

    def text_contains(self, key: str, token: str) -> bool:
        return token in self.text(key)

    def text_startswith(self, key: str, prefixes: str | tuple[str, ...]) -> bool:
        return self.text(key).startswith(prefixes)


class EvidenceAnalyzer:
    """Analyze evidence for vendor-specific patterns"""
    
    @staticmethod
    def get_vendor_hints(evidence: Dict[str, str]) -> List[str]:
        """Extract vendor hints from evidence"""
        hints: list[str] = []
        view = EvidenceView(evidence)

        # Vendor hints из SDP
        raw_hints = view.text("vendor_hints")
        if raw_hints:
            hints.extend([item.strip() for item in raw_hints.split(",") if item.strip()])

        # Анализ серверов
        for key in ("rtsp_server", "http_server"):
            server = view.text(key)
            if "dahua" in server:
                hints.append("dahua")
            elif "hikvision" in server:
                hints.append("hikvision")
            elif "axis" in server:
                hints.append("axis")

        # Анализ моделей
        model = view.text("onvif_model")
        if "ds-" in model or "dvr" in model:
            hints.append("hikvision")
        elif "dh-" in model or "ipc-h" in model:
            hints.append("dahua")

        return list(dict.fromkeys(hints))  # Уникальные хинты, сохраняем порядок
