from __future__ import annotations

from camera_probe.infrastructure.adapters.auto_import import auto_import_adapters

# Trigger adapter auto-registration
auto_import_adapters("camera_probe.infrastructure.adapters")
