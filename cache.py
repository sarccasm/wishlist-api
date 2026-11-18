import logging
import os
from typing import Optional

import redis

logger = logging.getLogger(__name__)

_client = redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379"),
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=1,
    retry_on_timeout=False,
)


class BestEffortCache:
    """Redis is optional; cache failures must not break application requests."""

    def get(self, key: str) -> Optional[str]:
        try:
            return _client.get(key)
        except redis.RedisError:
            logger.warning("Redis cache read failed; bypassing cache")
            return None

    def setex(self, key: str, seconds: int, value: str) -> None:
        try:
            _client.setex(key, seconds, value)
        except redis.RedisError:
            logger.warning("Redis cache write failed; continuing without cache")

    def delete(self, *keys: str) -> None:
        try:
            _client.delete(*keys)
        except redis.RedisError:
            logger.warning("Redis cache invalidation failed; continuing without cache")

    def ping(self) -> bool:
        try:
            return bool(_client.ping())
        except redis.RedisError:
            return False


cache = BestEffortCache()
