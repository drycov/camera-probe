from __future__ import annotations

import logging
from typing import Dict, Type, Optional

logger = logging.getLogger(__name__)


class ClientRegistry:
    """
    Registry of vendor-specific clients (ISAPI / CGI / ONVIF / etc).

    Usage:
        @ClientRegistry.register
        class HikvisionIsapiClient: ...
    """

    _registry: Dict[str, Type] = {}

    # ──────────────────────────────────────────────
    # Registration
    # ──────────────────────────────────────────────

    @classmethod
    def register(cls, client_cls: Type) -> Type:
        vendor = getattr(client_cls, "vendor", None)

        if not vendor:
            raise ValueError(
                f"Client {client_cls.__name__} has no 'vendor' attribute"
            )

        key = vendor.lower()

        if key in cls._registry:
            logger.warning(
                "Client for vendor '%s' already registered: %s → %s",
                key,
                cls._registry[key].__name__,
                client_cls.__name__,
            )

        cls._registry[key] = client_cls

        logger.debug(
            "Client registered | vendor=%s | class=%s",
            key,
            client_cls.__name__,
        )

        return client_cls

    # ──────────────────────────────────────────────
    # Lookup
    # ──────────────────────────────────────────────

    @classmethod
    def get(cls, vendor: str) -> Optional[Type]:
        if not vendor:
            return None
        return cls._registry.get(vendor.lower())

    @classmethod
    def all(cls) -> Dict[str, Type]:
        return dict(cls._registry)
