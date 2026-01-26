# camera_probe/cli/scan.py
from __future__ import annotations

import asyncio
import logging
from typing import Iterable, List

from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
)

from camera_probe import probe
from camera_probe.models.probe_result import ProbeResult

logger = logging.getLogger(__name__)


async def scan_subnet(
    ips: Iterable[str],
    *,
    concurrency: int = 10,
    username: str = "",
    password: str = "",
    force: bool = False,
) -> List[ProbeResult]:
    """
    Scan multiple IPs with bounded concurrency and Rich progress.

    Guarantees:
    - bounded parallelism
    - progress always advances
    - no task leaks
    - per-IP error isolation
    """

    semaphore = asyncio.Semaphore(concurrency)
    results: List[ProbeResult] = []

    async def worker(ip: str, progress: Progress, task_id: int) -> None:
        async with semaphore:
            try:
                result = await probe(
                    ip=ip,
                    username=username,
                    password=password,
                    force=force,
                )
                results.append(result)
            except Exception:
                logger.exception("scan probe failed | ip=%s", ip)
            finally:
                progress.advance(task_id)

    ip_list = list(ips)

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]Scanning"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        transient=True,
    ) as progress:
        task_id = progress.add_task("scan", total=len(ip_list))

        await asyncio.gather(
            *(worker(ip, progress, task_id) for ip in ip_list)
        )

    return results
