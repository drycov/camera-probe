from __future__ import annotations

from typing import Optional

from camera_probe.orchestrators.entrypoint import CameraProbe
from camera_probe.models.probe_result import ProbeResult, NetworkInfo, NtpInfo
from camera_probe.version import __version__


# ────────────────────────────────────────────────
# Singleton orchestrator
# ────────────────────────────────────────────────

_probe = CameraProbe()


# ────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────

async def probe(
    *,
    ip: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
    timeout: float = 5.0,
    force: bool = False,
) -> ProbeResult:
    """
    Asynchronously probe and identify an IP camera.

    This is the primary public API of the ``camera_probe`` library.
    The function is a **stable contract**: its signature and semantics
    must not change between minor versions.

    Args:
        ip:
            IP address of the camera (IPv4; IPv6 may be supported later).
            Example: ``"192.168.1.100"``

        username:
            Username for HTTP / ISAPI / CGI / VAPIX authentication.
            Optional; empty or None means anonymous access.

        password:
            Password for camera authentication.
            Optional.

        timeout:
            Maximum per-request timeout in seconds.
            Default: ``5.0``.

        force:
            If True, skip autodetection heuristics and force probing
            through all registered vendors/adapters.

    Returns:
        ProbeResult:
            Structured result of camera probing, including:
            - vendor, model, serial, firmware
            - confidence score
            - network information (NetworkInfo)
            - NTP configuration (NtpInfo)
            - partial error diagnostics (if any)

    Raises:
        asyncio.TimeoutError:
            Camera did not respond within timeout.

        ConnectionError:
            Network-level failure (connection refused, port closed, etc.).

        ValueError:
            Invalid input parameters (e.g. malformed IP).

        RuntimeError:
            Internal probing failure (rare; indicates a bug).

    Examples:
        >>> result = await probe(ip="192.168.1.64", timeout=8.0)
        >>> print(result.vendor, result.model, result.confidence)
        hikvision DS-2CD2143G0-I 0.98

        >>> result = await probe(
        ...     ip="10.10.10.50",
        ...     username="admin",
        ...     password="12345",
        ...     force=True,
        ... )

    Note:
        Internally, this function uses a singleton ``CameraProbe``
        instance to reuse registries, configuration, and caches.
    """
    return await _probe.probe(
        ip=ip,
        username=username or "",
        password=password or "",
        timeout=timeout,
        force=force,
    )


# ────────────────────────────────────────────────
# Public exports
# ────────────────────────────────────────────────

__all__ = [
    "probe",
    "CameraProbe",
    "ProbeResult",
    "NetworkInfo",
    "NtpInfo",
    "__version__",
]

__author__ = "Denis Rykov"
