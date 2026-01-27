from __future__ import annotations

import asyncio
from ipaddress import ip_network
import json
from typing import Optional

import typer
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
import logging
from camera_probe.application.dto.probe_request import ProbeRequest
from camera_probe.application.schema.probe_result import probe_result_schema
from camera_probe.application.serializers.probe_result import probe_result_to_dict
from camera_probe.bootstrap.probe import build_probe_service
from camera_probe.application.dto.scan_request import ScanRequest
from camera_probe.bootstrap import build_scan_service

logger = logging.getLogger(__name__)


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
    # json_schema: bool = typer.Option(
    #     False,
    #     "--json-schema",
    #     help="Print JSON Schema for ProbeResult and exit",
    # ),
) -> None:
    """
    Probe a single IP camera.
    """

    # ────────────────────────────────────────────────
    # Build request DTO
    # ────────────────────────────────────────────────

    request = ProbeRequest(
        ip=ip,
        username=username,
        password=password,
        timeout=timeout,
        force=force,
        prefer_force=prefer_force,
    )

    service = build_probe_service()

    # ────────────────────────────────────────────────
    # Execute use case
    # ────────────────────────────────────────────────

    try:
        result = asyncio.run(service.probe(request))
    except KeyboardInterrupt:
        typer.echo("Interrupted", err=True)
        raise typer.Exit(code=130)

    # ────────────────────────────────────────────────
    # Output
    # ────────────────────────────────────────────────

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


def schema() -> None:
    typer.echo(
        json.dumps(
            probe_result_schema(),
            indent=2,
            ensure_ascii=False,
        )
    )


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

    request = ScanRequest(
        cidr=cidr,
        username=username,
        password=password,
        timeout=timeout,
        concurrency=concurrency,
    )

    service = build_scan_service()
    results = []

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    )

    # 🔑 безопасный контейнер для task_id
    task_id_holder: dict[str, int] = {}

    def on_result(result):
        results.append(result)
        progress.advance(task_id_holder["task_id"])

    async def _run():
        with progress:
            task_id_holder["task_id"] = progress.add_task(
                "Scanning",
                total=total,
            )
            await service.scan(request, on_result=on_result)

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

def _print_human(result) -> None:
    typer.echo(f"IP:         {result.ip}")
    typer.echo(f"Vendor:     {result.vendor or '-'}")
    # typer.echo(f"Confidence: {result.confidence:.2f}")

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
            typer.echo(f"  Subnet:  {result.network.subnet}")

    if result.ntp:
        typer.echo("NTP:")
        if result.ntp.server:
            typer.echo(f"  Server:   {result.ntp.server}")
        if result.ntp.enabled is not None:
            typer.echo(f"  Enabled:  {result.ntp.enabled}")
