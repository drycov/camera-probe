from __future__ import annotations

from typing import Iterable

from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.box import SIMPLE

from camera_probe.models.probe_result import ProbeResult

console = Console()


def _status_cell(result: ProbeResult) -> Text:
    if result.is_success():
        return Text("OK", style="bold green")
    if result.vendor:
        return Text("PARTIAL", style="yellow")
    return Text("FAIL", style="bold red")


def _confidence_cell(confidence: float | None) -> Text:
    if confidence is None:
        return Text("—", style="dim")

    if confidence >= 0.9:
        style = "green"
    elif confidence >= 0.5:
        style = "yellow"
    else:
        style = "red"

    return Text(f"{confidence:.2f}", style=style)


def print_scan_results(results: Iterable[ProbeResult]) -> None:
    """
    Render scan results as a Rich table.

    Designed for:
    - large subnets
    - mixed vendors
    - CI / SSH terminals
    """

    table = Table(
        title="Camera scan results",
        title_style="bold cyan",
        header_style="bold white",
        box=SIMPLE,
        show_lines=False,
        expand=True,
    )

    table.add_column("IP", style="cyan", no_wrap=True)
    table.add_column("Vendor", style="magenta")
    table.add_column("Model", style="white", overflow="fold")
    table.add_column("Confidence", justify="right")
    table.add_column("Status", justify="center", no_wrap=True)
    
    

    for r in results:
        table.add_row(
            r.ip,
            r.vendor or "—",
            r.model or "—",
            _confidence_cell(r.confidence),
            _status_cell(r),
        )
    
    table.caption = (
    f"Total: {len(results)} | "
    f"OK: {sum(r.is_success() for r in results)} | "
    f"Failed: {sum(not r.vendor for r in results)}"
)

    console.print()
    console.print(table)
    console.print()
