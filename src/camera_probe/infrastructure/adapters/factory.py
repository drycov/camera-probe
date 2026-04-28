from __future__ import annotations

from camera_probe.domain.ports.adapter_factory import AdapterFactory
from camera_probe.domain.ports.adapter import CameraAdapter
from camera_probe.infrastructure.adapters.registry import AdapterRegistry
from camera_probe.infrastructure.vendor import normalize_vendor


class DefaultAdapterFactory(AdapterFactory):
    """
    Adapter factory with auto-registered adapters.
    """

    def create(
        self,
        *,
        vendor: str,
        ip: str,
        username: str | None,
        password: str | None,
        timeout: float,
    ) -> CameraAdapter:

        vendor_key = normalize_vendor(vendor)
        if not vendor_key:
            raise ValueError("Vendor is not defined")

        adapter_cls = AdapterRegistry.get(vendor_key)
        if not adapter_cls:
            raise ValueError(f"No adapter registered for vendor: {vendor_key}")

        return adapter_cls(
            ip=ip,
            username=username,
            password=password,
            timeout=timeout,
        )
