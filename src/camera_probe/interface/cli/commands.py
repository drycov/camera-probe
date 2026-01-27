from __future__ import annotations

import asyncio
import json
from ipaddress import ip_network
from typing import Optional, List

import typer
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from camera_probe.api import probe as probe_api
from camera_probe.api import scan as scan_api  # ⬅️ публичный scan
from camera_probe.application.serializers.probe_result import probe_result_to_dict
from camera_probe.domain.models.probe_result import ProbeResult

app = typer.Typer()


# ────────────────────────────────────────────────
# Probe command (PUBLIC API)
# ────────────────────────────────────────────────


@app.command()
def probe(
    ip: str = typer.Option(..., "--ip", help="IP address of the camera"),
    username: Optional[str] = typer.Option(None, "--user", help="Username"),
    password: Optional[str] = typer.Option(None, "--password", help="Password"),
    timeout: float = typer.Option(5.0, "--timeout", help="Request timeout (seconds)"),
    force: bool = typer.Option(False, "--force", help="Force probe (skip discovery)"),
    prefer_force: bool = typer.Option(
        False,
        "--prefer-force",
        help="Prefer force probe if credentials are present",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output result as JSON",
    ),
) -> None:
    """
    Probe a single IP camera.
    """

    try:
        result: ProbeResult = asyncio.run(
            probe_api(
                ip=ip,
                username=username,
                password=password,
                timeout=timeout,
                force=force,
                prefer_force=prefer_force,
            )
        )

    except KeyboardInterrupt:
        typer.echo("Interrupted", err=True)
        raise typer.Exit(code=130)

    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(
            json.dumps(
                probe_result_to_dict(result),
                indent=2,
                ensure_ascii=False,
            )
        )
        raise typer.Exit(code=0)

    _print_human(result)


# ────────────────────────────────────────────────
# Scan command (PUBLIC API)
# ────────────────────────────────────────────────


@app.command()
def scan(
    cidr: str = typer.Argument(..., help="CIDR to scan (e.g. 10.0.0.0/24)"),
    username: Optional[str] = typer.Option(None, "--user"),
    password: Optional[str] = typer.Option(None, "--password"),
    timeout: float = typer.Option(5.0, "--timeout"),
    concurrency: int = typer.Option(20, "--concurrency"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """
    Scan a CIDR for IP cameras.
    """

    hosts = list(ip_network(cidr, strict=False).hosts())
    total = len(hosts)
    results: List[ProbeResult] = []

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    )

    async def _run():
        with progress:
            task_id = progress.add_task("Scanning", total=total)

            async for result in scan_api(
                cidr=cidr,
                username=username,
                password=password,
                timeout=timeout,
                concurrency=concurrency,
            ):
                results.append(result)
                progress.advance(task_id)

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        typer.echo("Interrupted", err=True)
        raise typer.Exit(code=130)

    if json_output:
        typer.echo(
            json.dumps(
                [probe_result_to_dict(r) for r in results],
                indent=2,
                ensure_ascii=False,
            )
        )
        raise typer.Exit(code=0)

    for r in results:
        typer.echo(f"{r.ip:15} {r.vendor or '-':10} {r.confidence:.2f}")


# ────────────────────────────────────────────────
# Human-readable output
# ────────────────────────────────────────────────


def _print_human(result: ProbeResult) -> None:
    typer.echo(f"IP:         {result.ip}")
    typer.echo(f"Vendor:     {result.vendor or '-'}")

    if result.model:
        typer.echo(f"Model:      {result.model}")
    if result.serial:
        typer.echo(f"Serial:     {result.serial}")
    if result.mac:
        typer.echo(f"MAC:        {result.mac}")
    if result.firmware:
        typer.echo(f"Firmware:   {result.firmware}")

    if result.network:
        typer.echo("Network:")
        if result.network.ip:
            typer.echo(f"  IP:       {result.network.ip}")
        if result.network.gateway:
            typer.echo(f"  Gateway:  {result.network.gateway}")
        if result.network.mask:
            typer.echo(f"  Netmask:  {result.network.mask}")
        if result.network.subnet:
            typer.echo(f"  Subnet:   {result.network.subnet}")

    if result.ntp:
        typer.echo("NTP:")
        if result.ntp.server:
            typer.echo(f"  Server:   {result.ntp.server}")
        if result.ntp.enabled is not None:
            typer.echo(f"  Enabled:  {result.ntp.enabled}")
