# camera_probe/infrastructure/fingerprints/base.py
from __future__ import annotations
from abc import ABC, abstractmethod


class Fingerprint(ABC):
    """Base class for vendor fingerprints"""
    
    @abstractmethod
    def match(self, evidence: dict) -> bool:
        """Check if evidence matches this fingerprint"""
        pass
    
    @abstractmethod
    def vendor(self) -> str:
        """Get vendor name"""
        pass
    
    @abstractmethod
    def confidence(self) -> float:
        """Get confidence score (0.0 to 1.0)"""
        pass
    
    def priority(self) -> int:
        """Get priority for matching (higher = checked first)"""
        # По умолчанию используем уверенность как приоритет
        return int(self.confidence() * 100)
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__} ({self.vendor()})"