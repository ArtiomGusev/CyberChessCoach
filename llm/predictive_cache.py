from __future__ import annotations

try:
    from .fen_hash import fen_hash
    from .redis_client import redis_client
except ImportError:
    from fen_hash import fen_hash
    from redis_client import redis_client


def _pred_key(fen: str) -> str:
    return f"cc:pred:{fen_hash(fen)}"


async def store_predictions(fen: str, moves: list[str], ttl_seconds: int = 3600) -> None:
    if redis_client is None:
        return

    key = _pred_key(fen)
    try:
        await redis_client.delete(key)
        if moves:
            await redis_client.lpush(key, *moves)
            await redis_client.expire(key, ttl_seconds)
    except Exception:
        return


async def get_predictions(fen: str) -> list[str]:
    if redis_client is None:
        return []

    key = _pred_key(fen)
    try:
        return await redis_client.lrange(key, 0, -1)
    except Exception:
        return []
