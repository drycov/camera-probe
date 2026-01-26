# camera_probe/infrastructure/net/tcp.py
import asyncio


async def tcp_check(ip: str, port: int, timeout: float = 1.0) -> bool:
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False
