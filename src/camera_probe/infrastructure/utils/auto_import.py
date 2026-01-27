from __future__ import annotations

import importlib
import logging
import pkgutil


logger = logging.getLogger(__name__)


def auto_import(package_name: str, *, kind: str) -> None:
    """
    Recursively imports all modules under the given package.

    Used to trigger self-registration via decorators.

    Args:
        package_name: dotted package path
        kind: logical component name (for logs), e.g. 'adapter', 'device extractor'
    """
    try:
        package = importlib.import_module(package_name)
    except Exception as exc:
        logger.error("Failed to import %s package %s: %s", kind, package_name, exc)
        return

    if not hasattr(package, "__path__"):
        logger.warning("%s package %s has no __path__", kind, package_name)
        return

    for module_info in pkgutil.walk_packages(
        package.__path__,
        prefix=f"{package_name}.",
    ):
        module_name = module_info.name

        try:
            importlib.import_module(module_name)
            logger.debug("Auto-imported %s module: %s", kind, module_name)
        except Exception as exc:
            logger.exception(
                "Failed to auto-import %s module %s: %s",
                kind,
                module_name,
                exc,
            )
