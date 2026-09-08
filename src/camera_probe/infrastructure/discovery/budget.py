from __future__ import annotations

import asyncio
import os
import threading
from contextlib import asynccontextmanager
from typing import AsyncIterator


class DiscoveryBudget:
    """Process-wide, event-loop-independent concurrency budget."""

    def __init__(self, *, total: int = 16, tcp: int = 32, rtsp: int = 8, http: int = 4, onvif: int = 4) -> None:
        self._limits = {
            "total": max(1, total),
            "tcp": max(1, tcp),
            "rtsp": max(1, rtsp),
            "http": max(1, http),
            "onvif": max(1, onvif),
        }
        self._semaphores = {
            name: threading.BoundedSemaphore(value=limit)
            for name, limit in self._limits.items()
        }

    @classmethod
    def from_env(cls) -> "DiscoveryBudget":
        def get(name: str, default: int) -> int:
            try:
                return max(1, int(os.getenv(name, str(default))))
            except (TypeError, ValueError):
                return default

        return cls(
            total=get("CAMERA_PROBE_MAX_CONCURRENT", 16),
            tcp=get("CAMERA_PROBE_MAX_TCP", 32),
            rtsp=get("CAMERA_PROBE_MAX_RTSP", 8),
            http=get("CAMERA_PROBE_MAX_HTTP", 4),
            onvif=get("CAMERA_PROBE_MAX_ONVIF", 4),
        )

    @asynccontextmanager
    async def slot(self, name: str) -> AsyncIterator[None]:
        """Acquire a slot without blocking a worker thread."""
        semaphore = self._semaphores[name]
        while not semaphore.acquire(blocking=False):
            await asyncio.sleep(0.005)
        try:
            yield
        finally:
            semaphore.release()

    def limits(self) -> dict[str, int]:
        return dict(self._limits)


# Shared by all DiscoveryEngine instances in this process.
default_discovery_budget = DiscoveryBudget.from_env()
