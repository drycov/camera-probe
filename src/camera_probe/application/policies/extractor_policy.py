from __future__ import annotations

from enum import Enum


class ExtractorPolicy(str, Enum):
    """
    Defines behavior when extractor is missing.
    """

    STRICT = "strict"
    OPTIONAL = "optional"
