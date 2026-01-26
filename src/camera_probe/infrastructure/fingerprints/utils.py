# camera_probe/infrastructure/fingerprints/utils.py
from __future__ import annotations
import re
from typing import Dict, List, Pattern


class PatternMatcher:
    """Utility class for pattern matching in evidence"""
    
    @staticmethod
    def contains_any(text: str, patterns: List[str], case_sensitive: bool = False) -> bool:
        """Check if text contains any of the patterns"""
        if not text:
            return False
            
        if not case_sensitive:
            text = text.lower()
            patterns = [p.lower() for p in patterns]
            
        return any(pattern in text for pattern in patterns)
    
    @staticmethod
    def matches_any(text: str, regex_patterns: List[Pattern], case_sensitive: bool = False) -> bool:
        """Check if text matches any of the regex patterns"""
        if not text:
            return False
            
        if not case_sensitive:
            text = text.lower()
            
        return any(pattern.search(text) for pattern in regex_patterns)
    
    @staticmethod
    def extract_model_number(text: str) -> str | None:
        """Extract model number from text"""
        if not text:
            return None
            
        # Общие паттерны моделей камер
        patterns = [
            r'[A-Z]{2,4}-[A-Z0-9-]{5,15}',  # DS-2CD2143G0-I, DH-IPC-HFWXXXX
            r'IPC-[A-Z0-9-]{5,15}',  # IPC-HDWXXXX
            r'[A-Z]{3,4}\d{3,6}[A-Z]*',  # ABC123D, ABCD1234
            r'MODEL[:=]\s*([A-Z0-9-]+)',  # MODEL: DS-2CD2143G0-I
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
                
        return None


class EvidenceAnalyzer:
    """Analyze evidence for vendor-specific patterns"""
    
    @staticmethod
    def get_vendor_hints(evidence: Dict[str, str]) -> List[str]:
        """Extract vendor hints from evidence"""
        hints = []
        
        # Vendor hints из SDP
        if "vendor_hints" in evidence:
            hints.extend(evidence["vendor_hints"].lower().split(','))
        
        # Анализ серверов
        for key in ["rtsp_server", "http_server"]:
            if key in evidence:
                server = evidence[key].lower()
                if "dahua" in server:
                    hints.append("dahua")
                elif "hikvision" in server:
                    hints.append("hikvision")
                elif "axis" in server:
                    hints.append("axis")
        
        # Анализ моделей
        if "onvif_model" in evidence:
            model = evidence["onvif_model"].lower()
            if "ds-" in model or "dvr" in model:
                hints.append("hikvision")
            elif "dh-" in model or "ipc-h" in model:
                hints.append("dahua")
        
        return list(set(hints))  # Уникальные хинты