from __future__ import annotations

import asyncio
import logging
import typer

from camera_probe import probe
from camera_probe.adapters import debug as debug_adapters
from camera_probe.cli.output import print_result
from camera_probe.cli.scan_output import print_scan_results
from camera_probe.cli.scan import scan_subnet
from camera_probe.utils.logging import setup_logging
from camera_probe.utils.net import iter_subnet_hosts

app = typer.Typer(
    name="camera-probe",
    help="Async IP camera probing utility",
    add_completion=True,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Logging helper
# ──────────────────────────────────────────────

def _setup_cli_logging(verbosity: int) -> None:
    setup_logging(
        verbose=verbosity > 0,
        cli=True,
        force=True,
    )


# ──────────────────────────────────────────────
# Default entrypoint (python -m camera_probe)
# ──────────────────────────────────────────────

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    ip: str = typer.Option(None, help="Camera IP address"),
    username: str = typer.Option("", help="Username"),
    password: str = typer.Option("", help="Password"),
    force: bool = typer.Option(False, help="Force probing all adapters"),
    verbose: int = typer.Option(0, "-v", "--verbose", count=True),
) -> None:
    if ctx.invoked_subcommand is not None:
        return

    if not ip:
        typer.echo("Missing --ip", err=True)
        raise typer.Exit(code=2)

    _setup_cli_logging(verbose)

    logger.info("CLI probe start | ip=%s | force=%s", ip, force)

    try:
        result = asyncio.run(
            probe(
                ip=ip,
                username=username,
                password=password,
                force=force,
            )
        )
        print_result(result)
        raise typer.Exit(code=0 if result.is_success() else 2)

    except KeyboardInterrupt:
        raise typer.Exit(code=130)


# ──────────────────────────────────────────────
# Explicit commands
# ──────────────────────────────────────────────

@app.command("probe")
def probe_cmd(
    ip: str = typer.Option(...),
    username: str = typer.Option(""),
    password: str = typer.Option(""),
    force: bool = typer.Option(False),
    verbose: int = typer.Option(0, "-v", "--verbose", count=True),
) -> None:
    _setup_cli_logging(verbose)

    logger.info("CLI probe start | ip=%s | force=%s", ip, force)

    try:
        result = asyncio.run(
            probe(
                ip=ip,
                username=username,
                password=password,
                force=force,
            )
        )
        print_result(result)
        raise typer.Exit(code=0 if result.is_success() else 2)

    except KeyboardInterrupt:
        raise typer.Exit(code=130)


@app.command()
def scan(
    subnet: str = typer.Option(..., help="IPv4 subnet (CIDR)"),
    username: str = typer.Option(""),
    password: str = typer.Option(""),
    concurrency: int = typer.Option(10),
    force: bool = typer.Option(False),
    verbose: int = typer.Option(0, "-v", "--verbose", count=True),
) -> None:
    _setup_cli_logging(verbose)

    ips = list(iter_subnet_hosts(subnet))
    logger.info("scan start | subnet=%s | hosts=%d", subnet, len(ips))

    try:
        results = asyncio.run(
            scan_subnet(
                ips,
                concurrency=concurrency,
                username=username,
                password=password,
                force=force,
            )
        )
    except KeyboardInterrupt:
        raise typer.Exit(code=130)

    print_scan_results(results)

    success = any(r.is_success() for r in results)
    raise typer.Exit(code=0 if success else 2)


@app.command("dump-detect")
def dump_detect(
    verbose: int = typer.Option(0, "-v", "--verbose", count=True),
) -> None:
    _setup_cli_logging(verbose)

    import json

    snapshot = debug_adapters(verbose=verbose > 0)
    typer.echo(json.dumps(snapshot, indent=2, ensure_ascii=False))
