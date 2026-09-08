from __future__ import annotations

import asyncio
import os
import threading
from contextlib import asynccontextmanager
from typing import AsyncIterator


class DiscoveryBudget:
    """Process-wide budget shared by every DiscoveryEngine/event loop."""

    def __init__(self, camera: int = 16, tcp: int = 32, rtsp: int = 8, http: int = 4, onvif: int = 4) -> None:
        self.camera = threading.BoundedSemaphore(max(1, camera))
        self.tcp = threading.BoundedSemaphore(max(1, tcp))
        self.rtsp = threading.BoundedSemaphore(max(1, rtsp))
        self.http = threading.BoundedSemaphore(max(1, http))
        self.onvif = threading.BoundedSemaphore(max(1, onvif))

    @classmethod
    def from_env(cls) -> "DiscoveryBudget":
        def read(name: str, default: int) -> int:
            try:
                return max(1, int(os.getenv(name, str(default))))
            except ValueError:
                return default
        return cls(
            camera=read("CAMERA_PROBE_MAX_CONCURRENT", 16),
            tcp=read("CAMERA_PROBE_MAX_TCP", 32),
            rtsp=read("CAMERA_PROBE_MAX_RTSP", 8),
            http=read("CAMERA_PROBE_MAX_HTTP", 4),
            onvif=read("CAMERA_PROBE_MAX_ONVIF", 4),
        )

    @asynccontextmanager
    async def acquire(self, resource: str) -> AsyncIterator[None]:
        semaphore = getattr(self, resource)
        await asyncio.to_thread(semaphore.acquire)
        try:
            yield
        finally:
            semaphore.release()


GLOBAL_DISCOVERY_BUDGET = DiscoveryBudget.from_env()
