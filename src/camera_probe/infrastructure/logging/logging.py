# camera_probe/logging.py
from __future__ import annotations

import logging
import sys

TRACE_LEVEL = 5


def _add_trace_level() -> None:
    if hasattr(logging, "TRACE"):
        return

    logging.TRACE = TRACE_LEVEL  # type: ignore[attr-defined]
    logging.addLevelName(TRACE_LEVEL, "TRACE")

    def trace(self, message, *args, **kwargs):
        if self.isEnabledFor(TRACE_LEVEL):
            self._log(TRACE_LEVEL, message, args, **kwargs)

    logging.Logger.trace = trace  # type: ignore[attr-defined]


def setup_logging(*, level: str = "INFO") -> None:
    """
    Setup application-wide logging.
    Must be called ONCE from CLI entrypoint.
    """

    _add_trace_level()

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(numeric_level)

    if root.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    root.addHandler(handler)
