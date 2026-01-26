from __future__ import annotations

from typing import Dict, Type, Optional, ClassVar, Final

from camera_probe.clients.base import BaseClient


class ClientRegistry:
    """
    Registry of camera API client classes by vendor.

    Responsibilities:
    - Single source of truth: vendor -> Client class
    - Safe registration (no duplicates, no overrides)
    - Vendor name normalization
    - Deterministic lookup
    - Test-friendly reset

    This registry is used by probes and adapters
    to resolve the correct low-level API client.
    """

    # vendor(lower) -> client class
    _registry: ClassVar[Dict[str, Type[BaseClient]]] = {}

    # cached snapshot
    _all_cache: ClassVar[Optional[Dict[str, Type[BaseClient]]]] = None

    # vendors that must never be overridden
    _protected_vendors: Final[frozenset[str]] = frozenset({"base"})

    # ──────────────────────────────────────────────
    # Registration
    # ──────────────────────────────────────────────

    @classmethod
    def register(cls, client_cls: Type[BaseClient]) -> Type[BaseClient]:
        """
        Decorator for client registration.

        Requirements:
        - client_cls must inherit from BaseClient
        - client_cls must define class attribute `vendor: str`
        """

        if not issubclass(client_cls, BaseClient):
            raise TypeError(
                f"{client_cls.__name__} must inherit from BaseClient"
            )

        vendor = getattr(client_cls, "vendor", None)
        if not vendor or not isinstance(vendor, str):
            raise ValueError(
                f"{client_cls.__name__} must define class attribute `vendor: str`"
            )

        norm_vendor = vendor.strip().lower()
        if not norm_vendor:
            raise ValueError(
                f"{client_cls.__name__}: vendor must not be empty"
            )

        if norm_vendor in cls._protected_vendors:
            raise RuntimeError(f"Vendor '{norm_vendor}' is protected")

        if norm_vendor in cls._registry:
            existing = cls._registry[norm_vendor].__name__
            raise RuntimeError(
                f"Vendor '{norm_vendor}' already registered to {existing}; "
                f"cannot register {client_cls.__name__}"
            )

        cls._registry[norm_vendor] = client_cls
        cls._all_cache = None  # invalidate cache

        return client_cls

    # ──────────────────────────────────────────────
    # Lookup
    # ──────────────────────────────────────────────

    @classmethod
    def get(cls, vendor: Optional[str]) -> Optional[Type[BaseClient]]:
        """
        Get client class by vendor name (case-insensitive).

        Returns None if vendor is unknown or empty.
        """
        if not vendor:
            return None
        return cls._registry.get(vendor.lower())

    @classmethod
    def all(cls) -> Dict[str, Type[BaseClient]]:
        """
        Return snapshot of registry (vendor -> client class).

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
