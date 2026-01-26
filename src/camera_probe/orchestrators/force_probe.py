from __future__ import annotations

import asyncio
import logging
from typing import Iterable, List, Optional, Type

from camera_probe.adapters.base import CameraAdapter
from camera_probe.models.probe_result import ProbeResult
from camera_probe.adapters.registry import AdapterRegistry

logger = logging.getLogger(__name__)


class ForceProbeOrchestrator:
    """
    Force probing orchestrator.

    Tries ALL available adapters with provided credentials and returns:
    - first good result (stop_on_success=True)
    - or best result by confidence (stop_on_success=False)
    """

    def __init__(
        self,
        adapters: Optional[Iterable[Type[CameraAdapter]]] = None,
        *,
        concurrency: int = 3,
        stop_on_success: bool = True,
        min_confidence: float = 0.5,
    ):
        self.adapters = list(adapters or AdapterRegistry.ordered())
        self.concurrency = concurrency
        self.stop_on_success = stop_on_success
        self.min_confidence = min_confidence

        if not self.adapters:
            raise ValueError("No adapters provided")

        logger.debug(
            "ForceProbeOrchestrator initialized | adapters=%d | concurrency=%d | "
            "stop_on_success=%s | min_conf=%.2f",
            len(self.adapters),
            concurrency,
            stop_on_success,
            min_confidence,
        )

    # ────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────

    async def run(
        self,
        ip: str,
        *,
        username: str = "",
        password: str = "",
        timeout: float = 5.0,
    ) -> ProbeResult:
        logger.info(
            "force_probe start | ip=%s | adapters=%d | timeout=%.1fs | creds=%s",
            ip, len(self.adapters), timeout, bool(username or password),
        )

        sem = asyncio.Semaphore(self.concurrency)

        async def run_adapter(adapter_cls: Type[CameraAdapter]) -> Optional[ProbeResult]:
            async with sem:
                return await self._probe_one(
                    adapter_cls,
                    ip=ip,
                    username=username,
                    password=password,
                    timeout=timeout,
                )

        tasks = [asyncio.create_task(run_adapter(a)) for a in self.adapters]

        best: Optional[ProbeResult] = None

        try:
            for task in asyncio.as_completed(tasks):
                result = await task

                if not self._is_good_result(result):
                    continue

                logger.info(
                    "force success | ip=%s | vendor=%s | conf=%.2f",
                    ip,
                    result.vendor,
                    result.confidence,
                )

                if not best or result.confidence > best.confidence:
                    best = result

                if self.stop_on_success:
                    logger.info("force early-stop | ip=%s", ip)
                    break

        finally:
            # Cancel remaining tasks
            for task in tasks:
                if not task.done():
                    task.cancel()

            await asyncio.gather(*tasks, return_exceptions=True)

        if best:
            return best

        logger.warning("force_probe no_success | ip=%s", ip)
        return self._failure(ip)

    # ────────────────────────────────────────────────
    # Adapter execution
    # ────────────────────────────────────────────────

    async def _probe_one(
        self,
        adapter_cls: Type[CameraAdapter],
        *,
        ip: str,
        username: str,
        password: str,
        timeout: float,
    ) -> Optional[ProbeResult]:
        adapter_name = adapter_cls.__name__

        logger.debug("force probing | ip=%s | adapter=%s", ip, adapter_name)

        try:
            adapter = adapter_cls(
                ip=ip,
                username=username,
                password=password,
                timeout=timeout,
            )

            result = await adapter.probe_async()

            if result:
                logger.debug(
                    "adapter result | ip=%s | adapter=%s | vendor=%s | conf=%.2f",
                    ip,
                    adapter_name,
                    result.vendor or "—",
                    result.confidence,
                )

            return result

        except asyncio.CancelledError:
            logger.debug("adapter cancelled | ip=%s | adapter=%s", ip, adapter_name)
            raise

        except Exception:
            logger.exception("adapter failed | ip=%s | adapter=%s", ip, adapter_name)
            return None

    # ────────────────────────────────────────────────
    # Policy helpers
    # ────────────────────────────────────────────────

    def _is_good_result(self, result: Optional[ProbeResult]) -> bool:
        return bool(
            result
            and result.vendor
            and result.error is None
            and result.confidence >= self.min_confidence
        )

    def _failure(self, ip: str) -> ProbeResult:
        return ProbeResult(
            ip=ip,
            vendor=None,
            confidence=0.0,
            error="no_adapter_succeeded",
            raw={
                "tried_adapters": [a.__name__ for a in self.adapters],
                "reason": "no_adapter_produced_valid_result",
            },
        )

async def force_probe(
    ip: str,
    *,
    username: str = "",
    password: str = "",
    timeout: float = 5.0,
    concurrency: int = 3,
    stop_on_success: bool = True,
    min_confidence: float = 0.5,
) -> ProbeResult:
    orch = ForceProbeOrchestrator(
        concurrency=concurrency,
        stop_on_success=stop_on_success,
        min_confidence=min_confidence,
    )
    return await orch.run(
        ip=ip,
        username=username,
        password=password,
        timeout=timeout,
    )
