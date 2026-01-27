from __future__ import annotations
import logging

import typer

from camera_probe.infrastructure.logging.logging import setup_logging,TRACE_LEVEL

from camera_probe.interface.cli.commands import probe, scan


_app = typer.Typer(
    name="camera-probe",
    help="Async IP camera probing toolkit",
    add_completion=False,
)


@_app.callback()
def main(
    verbose: int = typer.Option(
        0,
        "-v",
        "--verbose",
        count=True,
        help="Increase verbosity (-v = DEBUG, -vv = TRACE)",
    ),
) -> None:
    """
    camera-probe CLI entrypoint.
    """

    if verbose >= 2:
        level = "TRACE"
    elif verbose == 1:
        level = "DEBUG"
    else:
        level = "INFO"
    
    logging.basicConfig(level=TRACE_LEVEL)

    setup_logging(level=level)


# Explicit command registration
_app.command("probe")(probe)
_app.command("scan")(scan)


def main() -> None:

    _app()
