# camera_probe/application/serializers/probe_result.py
from __future__ import annotations

from dataclasses import is_dataclass, fields
from typing import Any, Dict

from camera_probe.domain.models.probe_result import ProbeResult


def serialize_dataclass(obj) -> Dict[str, Any]:
    """
    Generic serializer for dataclasses with slots.
    """
    result = {}
    for f in fields(obj):
        value = getattr(obj, f.name)
        if is_dataclass(value):
            result[f.name] = serialize_dataclass(value)
        else:
            result[f.name] = value
    return result


def probe_result_to_dict(result: ProbeResult) -> Dict[str, Any]:
    """
    Serialize ProbeResult into JSON-safe dict.
    """
    return serialize_dataclass(result)
