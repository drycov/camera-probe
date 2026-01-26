# camera_probe/discovery/registry.py
from __future__ import annotations

from typing import Dict, Type, Optional, ClassVar, Final, Iterable

from camera_probe.adapters.base import CameraAdapter


class AdapterRegistry:
    """
    Registry of discovery adapters by vendor.

    Responsibilities:
    - Single source of truth: vendor -> CameraAdapter class
    - Safe registration (no duplicates, no overrides)
    - Vendor name normalization
    - Deterministic adapter ordering
    - Test-friendly reset
    """

    # vendor(lower) -> adapter class
    _registry: ClassVar[Dict[str, Type[CameraAdapter]]] = {}

    # cached ordered snapshot
    _ordered_cache: ClassVar[Optional[list[Type[CameraAdapter]]]] = None

    # vendors that must never be overridden
    _protected_vendors: Final[frozenset[str]] = frozenset({"base"})

    # ──────────────────────────────────────────────
    # Registration
    # ──────────────────────────────────────────────

    @classmethod
    def register(cls, adapter_cls: Type[CameraAdapter]) -> Type[CameraAdapter]:
        """
        Decorator for adapter registration.

        Requirements:
        - adapter_cls must subclass CameraAdapter
        - adapter_cls must define class attribute `vendor: str`
        """

        if not issubclass(adapter_cls, CameraAdapter):
            raise TypeError(
                f"{adapter_cls.__name__} must inherit from CameraAdapter"
            )

        vendor = getattr(adapter_cls, "vendor", None)
        if not vendor or not isinstance(vendor, str):
            raise ValueError(
                f"{adapter_cls.__name__} must define class attribute `vendor: str`"
            )

        norm_vendor = vendor.strip().lower()
        if not norm_vendor:
            raise ValueError(
                f"{adapter_cls.__name__}: vendor must not be empty"
            )

        if norm_vendor in cls._protected_vendors:
            raise RuntimeError(f"Vendor '{norm_vendor}' is protected")

        if norm_vendor in cls._registry:
            existing = cls._registry[norm_vendor].__name__
            raise RuntimeError(
                f"Vendor '{norm_vendor}' already registered to {existing}; "
                f"cannot register {adapter_cls.__name__}"
            )

        cls._registry[norm_vendor] = adapter_cls
        cls._ordered_cache = None  # invalidate cache

        return adapter_cls

    # ──────────────────────────────────────────────
    # Lookup
    # ──────────────────────────────────────────────

    @classmethod
    def get(cls, vendor: Optional[str]) -> Optional[Type[CameraAdapter]]:
        """
        Get adapter class by vendor name (case-insensitive).
        """
        if not vendor:
            return None
        return cls._registry.get(vendor.lower())

    @classmethod
    def ordered(cls) -> list[Type[CameraAdapter]]:
        """
        Return adapters in deterministic order.

        Order is registration order.
        Returned list is safe to modify by caller.
        """
        if cls._ordered_cache is None:
            cls._ordered_cache = list(cls._registry.values())
        return list(cls._ordered_cache)

    @classmethod
    def all(cls) -> Dict[str, Type[CameraAdapter]]:
        """
        Return snapshot of registry (vendor -> adapter).
        """
        return dict(cls._registry)

    @classmethod
    def registered_vendors(cls) -> list[str]:
        """Return sorted list of registered vendor names."""
        return sorted(cls._registry.keys())

    # ──────────────────────────────────────────────
    # Test support
    # ──────────────────────────────────────────────

    @classmethod
    def clear(cls, *, allow_protected: bool = False) -> None:
        """
        Clear registry (intended for tests).

        By default protected vendors are preserved.
        """
        if allow_protected:
            cls._registry.clear()
        else:
            cls._registry = {
                k: v
                for k, v in cls._registry.items()
                if k in cls._protected_vendors
            }

        cls._ordered_cache = None
