from __future__ import annotations

from camera_probe.infrastructure.logging.logging import setup_logging


def apply_verbosity(verbose: int) -> None:
    if verbose >= 2:
        level = "TRACE"
    elif verbose == 1:
        level = "DEBUG"
    else:
        level = "INFO"

    setup_logging(level=level)
