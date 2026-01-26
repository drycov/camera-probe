from __future__ import annotations

from typing import Dict, Type, Optional, ClassVar, Final

from camera_probe.probes.base import BaseProbe


class ProbeRegistry:
    """
    Registry of probe classes by vendor.

    Responsibilities:
    - Single source of truth: vendor -> Probe class
    - Safe registration (no overrides, no duplicates)
    - Vendor name normalization
    - Test-friendly reset
    """

    # vendor(lower) -> Probe class
    _registry: ClassVar[Dict[str, Type[BaseProbe]]] = {}

    # cached snapshot of registry
    _all_cache: ClassVar[Optional[Dict[str, Type[BaseProbe]]]] = None

    # vendors that must never be overridden
    _protected_vendors: Final[frozenset[str]] = frozenset({"base"})

    # ──────────────────────────────────────────────
    # Registration
    # ──────────────────────────────────────────────

    @classmethod
    def register(cls, probe_cls: Type[BaseProbe]) -> Type[BaseProbe]:
        """
        Decorator for probe registration.

        Requirements:
        - probe_cls must subclass BaseProbe
        - probe_cls must define class attribute `vendor: str`
        """

        if not issubclass(probe_cls, BaseProbe):
            raise TypeError(
                f"{probe_cls.__name__} must inherit from BaseProbe"
            )

        vendor = getattr(probe_cls, "vendor", None)
        if not vendor or not isinstance(vendor, str):
            raise ValueError(
                f"{probe_cls.__name__} must define class attribute `vendor: str`"
            )

        norm_vendor = vendor.strip().lower()

        if not norm_vendor:
            raise ValueError(
                f"{probe_cls.__name__}: vendor must not be empty"
            )

        if norm_vendor in cls._protected_vendors:
            raise RuntimeError(f"Vendor '{norm_vendor}' is protected")

        if norm_vendor in cls._registry:
            existing = cls._registry[norm_vendor].__name__
            raise RuntimeError(
                f"Vendor '{norm_vendor}' already registered to {existing}; "
                f"cannot register {probe_cls.__name__}"
            )

        cls._registry[norm_vendor] = probe_cls
        cls._all_cache = None  # invalidate cache

        return probe_cls

    # ──────────────────────────────────────────────
    # Lookup
    # ──────────────────────────────────────────────

    @classmethod
    def get(cls, vendor: Optional[str]) -> Optional[Type[BaseProbe]]:
        """
        Get probe class by vendor name.

        Vendor name is case-insensitive.
        Returns None if vendor is unknown or empty.
        """
        if not vendor:
            return None
        return cls._registry.get(vendor.lower())

    @classmethod
    def all(cls) -> Dict[str, Type[BaseProbe]]:
        """
        Return a snapshot of the registry.

        Returned dict is safe to modify by caller.
        """
        if cls._all_cache is None:
            cls._all_cache = dict(cls._registry)
        return dict(cls._all_cache)

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

        cls._all_cache = None
