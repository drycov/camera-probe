# camera_probe/infrastructure/adapters/base.py
from __future__ import annotations

from camera_probe.domain.ports.adapter import CameraAdapter



class BaseCameraAdapter(CameraAdapter):
    """
    Shared base class for vendor adapters.
    """

    def __init__(
        self,
        *,
        ip: str,
        username: str | None,
        password: str | None,
        timeout: float,
    ) -> None:
        self.ip = ip
        self.username = username
        self.password = password
        self.timeout = timeout
