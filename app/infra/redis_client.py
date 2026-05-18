import os

import redis.asyncio as aioredis

_redis: aioredis.Redis | None = None


def init() -> None:
    global _redis
    url = os.environ["REDIS_URL"]
    _redis = aioredis.from_url(url, decode_responses=True)


def client() -> aioredis.Redis:
    assert _redis is not None, "call init() first"
    return _redis
