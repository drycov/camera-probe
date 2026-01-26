# camera_probe/cli/output.py
from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.table import Table
from rich.text import Text

from camera_probe.models.probe_result import ProbeResult

console = Console()


def _val(v: Any) -> str:
    return str(v) if v not in (None, "", [], {}) else "—"


def _confidence_text(conf: float | None) -> Text:
    if conf is None:
        return Text("—", style="dim")

    if conf >= 0.9:
        return Text(str(conf), style="bold green")
    if conf >= 0.6:
        return Text(str(conf), style="yellow")
    return Text(str(conf), style="red")


def print_result(result: ProbeResult) -> None:
    """
    Pretty Rich table output for a single ProbeResult.
    """

    table = Table(
        title=f"Camera probe result — {result.ip}",
        title_style="bold cyan",
        show_header=False,
        box=None,                 # ← без рамок (важно)
        pad_edge=False,
        highlight=True,
    )

    table.add_column("Field", style="bold", no_wrap=True)
    table.add_column("Value", overflow="fold")

    # ─── Identity ───────────────────────────────
    table.add_row("Vendor", _val(result.vendor))
    table.add_row("Model", _val(result.model))
    table.add_row("Serial", _val(result.serial))
    table.add_row("MAC", _val(result.mac))
    table.add_row("Firmware", _val(result.firmware))
    table.add_row("Confidence", _confidence_text(result.confidence))

    # ─── Network ────────────────────────────────
    if result.network:
        table.add_section()
        table.add_row(Text("Network", style="bold cyan"), "")

        table.add_row("  IP", _val(result.network.ip))
        table.add_row("  Mask", _val(result.network.netmask))
        table.add_row("  CIDR", _val(result.network.cidr))
        table.add_row("  Gateway", _val(result.network.gateway))

        if result.network.gateway_in_subnet is not None:
            gw_style = "green" if result.network.gateway_in_subnet else "red"
            table.add_row(
                "  GW OK",
                Text(
                    "yes" if result.network.gateway_in_subnet else "no",
                    style=gw_style,
                ),
            )

    # ─── NTP ────────────────────────────────────
    if result.ntp:
        table.add_section()
        table.add_row(Text("NTP", style="bold cyan"), "")

        table.add_row("  Enabled", _val(result.ntp.enabled))
        table.add_row("  Server", _val(result.ntp.server))
        table.add_row("  Port", _val(result.ntp.port))
        table.add_row("  Interval", _val(result.ntp.interval))

    # ─── Error ──────────────────────────────────
    if result.error:
        table.add_section()
        table.add_row(
            Text("Error", style="bold red"),
            Text(result.error, style="red"),
        )

    console.print()
    console.print(table)
    console.print()
