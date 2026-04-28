from __future__ import annotations

import argparse
from collections.abc import Sequence

from camera_probe.interface.cli.commands import run_probe, run_scan
from camera_probe.interface.cli.verbosity import apply_verbosity


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="camera-probe",
        description="Async IP camera probing toolkit",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="global_verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v = DEBUG, -vv = TRACE)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    probe_parser = subparsers.add_parser(
        "probe",
        help="Probe a single IP camera.",
        description="Probe a single IP camera.",
    )
    probe_parser.add_argument("--ip", required=True, help="IP address of the camera")
    probe_parser.add_argument("--user", dest="username", help="Username")
    probe_parser.add_argument("--password", help="Password")
    probe_parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Request timeout (seconds)",
    )
    probe_parser.add_argument(
        "--force",
        action="store_true",
        help="Force probe (skip discovery)",
    )
    probe_parser.add_argument(
        "--prefer-force",
        action="store_true",
        help="Prefer force probe if credentials are present",
    )
    probe_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output result as JSON",
    )
    probe_parser.add_argument(
        "-v",
        "--verbose",
        dest="command_verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v = DEBUG, -vv = TRACE)",
    )

    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan a CIDR for IP cameras.",
        description="Scan a CIDR for IP cameras.",
    )
    scan_parser.add_argument("cidr", help="CIDR to scan (e.g. 10.0.0.0/24)")
    scan_parser.add_argument("--user", dest="username", help="Username")
    scan_parser.add_argument("--password", help="Password")
    scan_parser.add_argument("--timeout", type=float, default=5.0)
    scan_parser.add_argument("--concurrency", type=int, default=20)
    scan_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output result as JSON",
    )
    scan_parser.add_argument(
        "-v",
        "--verbose",
        dest="command_verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v = DEBUG, -vv = TRACE)",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    global_verbose = getattr(args, "global_verbose", 0) or 0
    apply_verbosity(global_verbose)

    if args.command == "probe":
        run_probe(args, global_verbose=global_verbose)
        return

    if args.command == "scan":
        run_scan(args, global_verbose=global_verbose)
        return

    parser.error(f"Unknown command: {args.command}")
