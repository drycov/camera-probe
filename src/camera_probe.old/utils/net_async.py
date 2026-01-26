import asyncio
import logging
from typing import Tuple, Literal
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────
# Constants
# ────────────────────────────────────────────────

DEFAULT_TCP_TIMEOUT = 1.5
CACHE_TTL_SECONDS = 60
CACHE_MAX_SIZE = 8192

# ────────────────────────────────────────────────
# Global cache (async-safe via lock)
# ────────────────────────────────────────────────

_tcp_cache: TTLCache[Tuple[str, int], bool] = TTLCache(
    maxsize=CACHE_MAX_SIZE,
    ttl=CACHE_TTL_SECONDS,
)
_tcp_cache_lock = asyncio.Lock()

# ────────────────────────────────────────────────
# Core TCP check
# ────────────────────────────────────────────────


async def tcp_check(
    ip: str,
    port: int,
    timeout: float = DEFAULT_TCP_TIMEOUT,
    *,
    use_cache: bool = True,
) -> bool:
    """
    Асинхронно проверяет доступность TCP-порта.

    Кэшируются ТОЛЬКО успешные соединения.
    Отрицательные результаты не кэшируются намеренно.
    """

    if not (1 <= port <= 65535):
        raise ValueError(f"Invalid port number: {port}")

    key = (ip, port)

    if use_cache:
        async with _tcp_cache_lock:
            cached = _tcp_cache.get(key)
        if cached is True:
            logger.debug("tcp_check cache hit ip=%s port=%d → open", ip, port)
            return True

    logger.debug("tcp_check start ip=%s port=%d timeout=%.2fs", ip, port, timeout)

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=timeout,
        )

        writer.close()
        await writer.wait_closed()

        async with _tcp_cache_lock:
            _tcp_cache[key] = True

        logger.debug("tcp_check success ip=%s port=%d", ip, port)
        return True

    except asyncio.TimeoutError:
        logger.debug("tcp_check timeout ip=%s port=%d (%.2fs)", ip, port, timeout)
        return False

    except ConnectionRefusedError:
        logger.debug("tcp_check refused ip=%s port=%d", ip, port)
        return False

    except OSError as e:
        logger.debug(
            "tcp_check os_error ip=%s port=%d errno=%s",
            ip, port, e.errno,
        )
        return False

    except Exception:
        logger.exception("tcp_check unexpected error ip=%s port=%d", ip, port)
        return False


# ────────────────────────────────────────────────
# Verbose variant
# ────────────────────────────────────────────────


async def tcp_check_verbose(
    ip: str,
    port: int,
    timeout: float = DEFAULT_TCP_TIMEOUT,
    *,
    use_cache: bool = True,
) -> Tuple[bool, Literal["open", "timeout", "refused", "os_error", "error"]]:
    """
    Версия tcp_check с причиной результата.
    Контракт строго фиксирован.
    """

    if not (1 <= port <= 65535):
        raise ValueError(f"Invalid port number: {port}")

    key = (ip, port)

    if use_cache:
        async with _tcp_cache_lock:
            cached = _tcp_cache.get(key)
        if cached is True:
            logger.debug("tcp_check_verbose cache hit ip=%s port=%d → open", ip, port)
            return True, "open"

    logger.debug(
        "tcp_check_verbose start ip=%s port=%d timeout=%.2fs",
        ip, port, timeout,
    )

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=timeout,
        )

        writer.close()
        await writer.wait_closed()

        async with _tcp_cache_lock:
            _tcp_cache[key] = True

        logger.debug("tcp_check_verbose success ip=%s port=%d", ip, port)
        return True, "open"

    except asyncio.TimeoutError:
        logger.debug(
            "tcp_check_verbose timeout ip=%s port=%d (%.2fs)",
            ip, port, timeout,
        )
        return False, "timeout"

    except ConnectionRefusedError:
        logger.debug("tcp_check_verbose refused ip=%s port=%d", ip, port)
        return False, "refused"

    except OSError as e:
        logger.debug(
            "tcp_check_verbose os_error ip=%s port=%d errno=%s",
            ip, port, e.errno,
        )
        return False, "os_error"

    except Exception:
        logger.exception(
            "tcp_check_verbose unexpected error ip=%s port=%d",
            ip, port,
        )
        return False, "error"


# ────────────────────────────────────────────────
# Helpers (no cache)
# ────────────────────────────────────────────────


async def tcp_check_no_cache(
    ip: str,
    port: int,
    timeout: float = DEFAULT_TCP_TIMEOUT,
) -> bool:
    return await tcp_check(ip, port, timeout, use_cache=False)


async def tcp_check_verbose_no_cache(
    ip: str,
    port: int,
    timeout: float = DEFAULT_TCP_TIMEOUT,
) -> Tuple[bool, str]:
    return await tcp_check_verbose(ip, port, timeout, use_cache=False)
