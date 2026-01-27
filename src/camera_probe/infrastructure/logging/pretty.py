from __future__ import annotations

import textwrap
import xml.dom.minidom as minidom


def pretty_xml(raw: str) -> str:
    try:
        dom = minidom.parseString(raw.encode("utf-8"))
        return dom.toprettyxml(indent="  ")
    except Exception:
        return raw


def pretty_kv(raw: str) -> str:
    lines = []
    max_key = 0

    pairs = []
    for line in raw.splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        max_key = max(max_key, len(k))
        pairs.append((k, v))

    for k, v in pairs:
        lines.append(f"{k.ljust(max_key)} = {v}")

    return "\n".join(lines)


def indent_block(text: str, prefix: str = "│ ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())
