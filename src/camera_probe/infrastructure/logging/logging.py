# camera_probe/logging.py

from __future__ import annotations

import logging
import sys

import colorama

from camera_probe.infrastructure.logging.pretty import indent_block, pretty_kv, pretty_xml

colorama.just_fix_windows_console()

TRACE_LEVEL = 5


# ────────────────────────────────────────────────
# TRACE level
# ────────────────────────────────────────────────

def _add_trace_level() -> None:
    if hasattr(logging, "TRACE"):
        return

    logging.TRACE = TRACE_LEVEL  # type: ignore[attr-defined]
    logging.addLevelName(TRACE_LEVEL, "TRACE")

    def trace(self, message, *args, **kwargs):
        if self.isEnabledFor(TRACE_LEVEL):
            self._log(TRACE_LEVEL, message, args, **kwargs)

    logging.Logger.trace = trace  # type: ignore[attr-defined]


_add_trace_level()


# ────────────────────────────────────────────────
# Color formatter
# ────────────────────────────────────────────────


class ColorFormatter(logging.Formatter):
    RESET = "\033[0m"

    COLORS = {
        "TRACE": "\033[90m",
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[41m",
    }

    def format(self, record: logging.LogRecord) -> str:
        original_levelname = record.levelname
        original_msg = record.msg
        original_args = record.args

        color = self.COLORS.get(record.levelname, "")

        # ─────────────────────────────
        # Colorize level
        # ─────────────────────────────
        if color:
            record.levelname = f"{color}{record.levelname}{self.RESET}"

        # ─────────────────────────────
        # Pretty TRACE payload
        # ─────────────────────────────
        if original_levelname == "TRACE":
            msg = record.getMessage().strip()

            if msg.startswith("<") and msg.endswith(">"):
                msg = indent_block(pretty_xml(msg))

            elif "=" in msg and msg.count("=") >= 2:
                msg = indent_block(pretty_kv(msg))

            record.msg = msg
            record.args = ()

        try:
            return super().format(record)
        finally:
            record.levelname = original_levelname
            record.msg = original_msg
            record.args = original_args

# ────────────────────────────────────────────────
# Setup
# ────────────────────────────────────────────────

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
        for handler in root.handlers:
            handler.setLevel(numeric_level)
            if not isinstance(handler.formatter, ColorFormatter):
                handler.setFormatter(
                    ColorFormatter(
                        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",
                    )
                )
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)

    formatter = ColorFormatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler.setFormatter(formatter)
    root.addHandler(handler)
