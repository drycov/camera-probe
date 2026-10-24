from __future__ import annotations

import argparse
import asyncio
import json
import sys

from camera_probe.api import probe as probe_api
from camera_probe.api import scan as scan_api
from camera_probe.application.serializers.probe_result import probe_result_to_dict
from camera_probe.domain.models.probe_result import ProbeResult
from camera_probe.interface.cli.verbosity import apply_verbosity


def run_probe(args: argparse.Namespace, *, global_verbose: int = 0) -> None:
    apply_verbosity(max(global_verbose, getattr(args, "command_verbose", 0) or 0))

    try:
        result: ProbeResult = asyncio.run(
            probe_api(
                ip=args.ip,
                username=args.username,
                password=args.password,
                timeout=args.timeout,
                force=args.force,
                prefer_force=args.prefer_force,
            )
        )
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        raise SystemExit(130) from None
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None

    if args.json_output:
        _print_json(probe_result_to_dict(result))
        return

    _print_human(result)


def run_scan(args: argparse.Namespace, *, global_verbose: int = 0) -> None:
    apply_verbosity(max(global_verbose, getattr(args, "command_verbose", 0) or 0))

    json_output = bool(args.json_output)
    first_result = True
    if json_output:
        _configure_stdout()
        sys.stdout.write("[\n")

    async def _run() -> None:
        nonlocal first_result
        async for result in scan_api(
            cidr=args.cidr,
            username=args.username,
            password=args.password,
            timeout=args.timeout,
            concurrency=args.concurrency,
        ):
            if json_output:
                if not first_result:
                    sys.stdout.write(",\n")
                sys.stdout.write(
                    json.dumps(
                        probe_result_to_dict(result),
                        indent=2,
                        ensure_ascii=False,
                    )
                )
                sys.stdout.flush()
                first_result = False
            else:
                print(f"{result.ip:15} {result.vendor or '-':10} {result.confidence:.2f}")

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        raise SystemExit(130) from None
    finally:
        if json_output:
            sys.stdout.write("]\n" if first_result else "\n]\n")
            sys.stdout.flush()


def _configure_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _print_json(payload: object) -> None:
    _configure_stdout()
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _print_human(result: ProbeResult) -> None:
    print(f"IP:         {result.ip}")
    print(f"Vendor:     {result.vendor or '-'}")

    if result.model:
        print(f"Model:      {result.model}")
    if result.serial:
        print(f"Serial:     {result.serial}")
    if result.mac:
        print(f"MAC:        {result.mac}")
    if result.firmware:
        print(f"Firmware:   {result.firmware}")

    if result.network:
        print("Network:")
        if result.network.ip:
            print(f"  IP:       {result.network.ip}")
        if result.network.gateway:
            print(f"  Gateway:  {result.network.gateway}")
        if result.network.mask:
            print(f"  Netmask:  {result.network.mask}")
        if result.network.subnet:
            print(f"  Subnet:   {result.network.subnet}")

    if result.ntp:
        print("NTP:")
        if result.ntp.server:
            print(f"  Server:   {result.ntp.server}")
        if result.ntp.enabled is not None:
            print(f"  Enabled:  {result.ntp.enabled}")
