# camera_probe/application/schema/probe_result.py
from __future__ import annotations

from typing import Any, Dict


def probe_result_schema() -> Dict[str, Any]:
    """
    JSON Schema for ProbeResult (public contract).
    """
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "ProbeResult",
        "type": "object",
        "required": ["ip", "confidence"],
        "properties": {
            "ip": {"type": "string", "format": "ipv4"},
            "vendor": {"type": ["string", "null"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},

            "model": {"type": ["string", "null"]},
            "serial": {"type": ["string", "null"]},
            "mac": {"type": ["string", "null"]},
            "firmware": {"type": ["string", "null"]},

            "network": {
                "type": ["object", "null"],
                "properties": {
                    "ip": {"type": ["string", "null"]},
                    "mask": {"type": ["string", "null"]},
                    "cidr": {"type": ["integer", "null"]},
                    "gateway": {"type": ["string", "null"]},
                    "mac": {"type": ["string", "null"]},
                    "gateway_in_subnet": {"type": ["boolean", "null"]},
                },
                "additionalProperties": False,
            },

            "ntp": {
                "type": ["object", "null"],
                "properties": {
                    "enabled": {"type": ["boolean", "null"]},
                    "server": {"type": ["string", "null"]},
                    "timezone": {"type": ["string", "null"]},
                    "port": {"type": ["integer", "null"]},
                    "interval": {"type": ["integer", "null"]},
                },
                "additionalProperties": False,
            },

            "raw": {
                "type": "object",
                "additionalProperties": True,
            },
        },
        "additionalProperties": False,
    }
