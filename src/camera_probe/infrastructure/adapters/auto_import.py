from __future__ import annotations

import pkgutil
import importlib
import logging

logger = logging.getLogger(__name__)


def auto_import_adapters(package_name: str) -> None:
    """
    Recursively imports all modules under the given package.
    Required to trigger adapter self-registration.
    """
    try:
        package = importlib.import_module(package_name)
    except Exception as e:
        logger.error("Failed to import adapters package %s: %s", package_name, e)
        return

    if not hasattr(package, "__path__"):
        logger.warning("Package %s has no __path__", package_name)
        return

    for module_info in pkgutil.walk_packages(
        package.__path__,
        prefix=f"{package_name}.",
    ):
        module_name = module_info.name

        try:
            importlib.import_module(module_name)
            logger.debug("Auto-imported adapter module: %s", module_name)
        except Exception as e:
            logger.error(
                "Failed to auto-import adapter module %s: %s",
                module_name,
                e,
            )
