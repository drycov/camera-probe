# camera_probe/infrastructure/discovery/tcp.py
from __future__ import annotations

import asyncio
import logging
from typing import Iterable

from camera_probe.infrastructure.discovery.budget import default_discovery_budget

logger = logging.getLogger(__name__)


async def tcp_probe_ports(
    ip: str,
    ports: Iterable[int],
    timeout: float = 1.0,
) -> list[int]:
    """Return open TCP ports with a process-wide connection budget."""
    open_ports: list[int] = []

    async def _probe(port: int) -> None:
        logger.trace("TCP connect attempt: %s:%d", ip, port)
        try:
            async with default_discovery_budget.slot("tcp"):
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, port),
                    timeout=timeout,
                )
                writer.close()
                await writer.wait_closed()
            open_ports.append(port)
            logger.debug("TCP port open: %s:%d", ip, port)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.trace("TCP port closed: %s:%d", ip, port)

    await asyncio.gather(*[_probe(p) for p in ports])
    return open_ports
