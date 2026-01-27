from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Optional

logger = logging.getLogger(__name__)

def extract_default_ns(root: ET.Element) -> dict[str, str]:
    if root.tag.startswith("{"):
        uri = root.tag.split("}")[0][1:]
        return {"ns": uri}
    return {}


def parse_xml(raw: str) -> Optional[ET.Element]:
    """
    Safely parse XML string into ElementTree root.

    Guarantees:
    - Never raises
    - Returns None on invalid / empty XML
    - Handles leading garbage (BOM, whitespace)
    """

    if not raw:
        return None

    raw = raw.strip()
    if not raw:
        return None

    try:
        return ET.fromstring(raw)
    except ET.ParseError:
        logger.debug("xml parse failed (first 200 chars): %r", raw[:200])
        return None
