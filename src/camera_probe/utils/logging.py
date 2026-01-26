# camera_probe/utils/logging.py
"""
Logging utilities for camera_probe (Rich-based).

Principles:
- Quiet by default (WARNING+)
- Verbose enables DEBUG
- Rich rendering for CLI
- Library-safe (NullHandler)
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

from rich.logging import RichHandler

__all__ = ["setup_logging", "get_logger"]

_CAMERA_PROBE_NS = "camera_probe"


# ────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────

def setup_logging(
    *,
    verbose: bool = False,
    cli: bool = False,
    force: bool = False,
    logger_name: Optional[str] = None,
) -> None:
    """
    Configure logging.

    Behaviour:
    - Default CLI: WARNING+
    - verbose=True: DEBUG
    - CLI: RichHandler
    - Library: NullHandler only
    """

    if not force and getattr(setup_logging, "_configured", False):
        return

    level = logging.DEBUG if verbose else logging.WARNING

    if cli:
        _configure_cli(level)
    else:
        _configure_library(level, logger_name)

    _suppress_noisy_loggers()

    setup_logging._configured = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    if name:
        return logging.getLogger(f"{_CAMERA_PROBE_NS}.{name}")
    return logging.getLogger(_CAMERA_PROBE_NS)


# ────────────────────────────────────────────────
# CLI configuration (Rich)
# ────────────────────────────────────────────────

def _configure_cli(level: int) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    handler = RichHandler(
        level=level,
        console=None,              # default Rich console
        show_time=True,
        show_level=True,
        show_path=False,           # ← важно, иначе шум
        rich_tracebacks=True,
        tracebacks_show_locals=False,
    )

    # RichHandler сам форматирует, formatter НЕ нужен
    root.addHandler(handler)


# ────────────────────────────────────────────────
# Library-safe configuration
# ────────────────────────────────────────────────

def _configure_library(level: int, extra_logger: Optional[str]) -> None:
    base_logger = logging.getLogger(_CAMERA_PROBE_NS)
    base_logger.setLevel(level)

    if not any(isinstance(h, logging.NullHandler) for h in base_logger.handlers):
        base_logger.addHandler(logging.NullHandler())

    if extra_logger:
        logging.getLogger(extra_logger).setLevel(level)


# ────────────────────────────────────────────────
# Noise suppression
# ────────────────────────────────────────────────

def _suppress_noisy_loggers() -> None:
    noisy = {
        "asyncio": logging.WARNING,
        "aiohttp": logging.WARNING,
        "urllib3": logging.WARNING,
        "httpcore": logging.WARNING,
        "httpx": logging.WARNING,
        "charset_normalizer": logging.WARNING,
    }

    for name, level in noisy.items():
        logging.getLogger(name).setLevel(level)
