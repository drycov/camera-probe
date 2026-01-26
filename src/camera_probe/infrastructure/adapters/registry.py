from __future__ import annotations
import logging
from typing import Type, Dict
from camera_probe.domain.ports.adapter import CameraAdapter

logger = logging.getLogger(__name__)


class AdapterRegistry:
    _adapters: Dict[str, Type[CameraAdapter]] = {}

    @classmethod
    def register(cls, vendor: str, adapter_cls: Type[CameraAdapter]) -> None:
        key = vendor.lower()
        cls._adapters[key] = adapter_cls
        logger.debug(
            "Adapter registered: vendor=%s class=%s",
            key,
            adapter_cls.__name__,
        )

    @classmethod
    def get(cls, vendor: str) -> Type[CameraAdapter] | None:
        return cls._adapters.get(vendor)

    @classmethod
    def all(cls) -> dict[str, Type[CameraAdapter]]:
        return dict(cls._adapters)
