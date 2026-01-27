from __future__ import annotations

import pkgutil
import importlib
import logging

logger = logging.getLogger(__name__)


def auto_import_network_extractors(package_name: str) -> None:
    try:
        package = importlib.import_module(package_name)
    except Exception as e:
        logger.error("Failed to import network package %s: %s", package_name, e)
        return

    if not hasattr(package, "__path__"):
        logger.warning("Package %s has no __path__", package_name)
        return

    for mod in pkgutil.walk_packages(
        package.__path__,
        prefix=f"{package_name}.",
    ):
        try:
            importlib.import_module(mod.name)
            logger.debug("Auto-imported network extractor: %s", mod.name)
        except Exception as e:
            logger.error(
                "Failed to import network extractor %s: %s",
                mod.name,
                e,
            )
