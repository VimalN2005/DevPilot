import time
from collections import defaultdict
from typing import Optional
from fastapi import HTTPException, Request, status
try:
    import redis
except ImportError:
    redis = None
from app.config import settings

class RateLimiter:
    """Sliding-window rate limiter with Redis backend and in-memory fallback."""

    def __init__(self, requests_per_minute: int = 100):
        self.limit = requests_per_minute
        self.window = 60  # seconds
        self.redis_client = None
        self._memory_store = defaultdict(list)
        self._init_redis()

    def _init_redis(self):
        if redis is None:
            self.redis_client = None
            return
        try:
            r = redis.from_url(settings.REDIS_URL, socket_timeout=1)
            r.ping()
            self.redis_client = r
        except Exception:
            self.redis_client = None

    def is_allowed(self, identifier: str) -> tuple[bool, int, int]:
        """
        Check if request is allowed.
        Returns: (is_allowed, current_count, remaining)
        """
        now = time.time()
        clear_before = now - self.window
        key = f"devpilot:ratelimit:{identifier}"

        # 1. Try Redis sliding window
        if self.redis_client is not None:
            try:
                pipe = self.redis_client.pipeline()
                pipe.zremrangebyscore(key, 0, clear_before)
                pipe.zadd(key, {str(now): now})
                pipe.zcard(key)
                pipe.expire(key, self.window + 5)
                _, _, count, _ = pipe.execute()
                remaining = max(0, self.limit - count)
                return count <= self.limit, count, remaining
            except Exception:
                # Redis failed, fall back to memory
                self.redis_client = None

        # 2. In-memory sliding window fallback
        timestamps = self._memory_store[identifier]
        # Prune old timestamps
        self._memory_store[identifier] = [t for t in timestamps if t > clear_before]
        self._memory_store[identifier].append(now)
        count = len(self._memory_store[identifier])
        remaining = max(0, self.limit - count)
        return count <= self.limit, count, remaining


rate_limiter = RateLimiter(requests_per_minute=settings.RATE_LIMIT_PER_MINUTE)


async def check_rate_limit(request: Request):
    """FastAPI dependency for 100 req/min/user rate limit."""
    # Key by Authorization header or client IP
    auth_header = request.headers.get("Authorization", "")
    client_ip = request.client.host if request.client else "unknown"
    ident = auth_header if auth_header else client_ip

    allowed, count, remaining = rate_limiter.is_allowed(ident)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Maximum {settings.RATE_LIMIT_PER_MINUTE} requests/minute allowed.",
            headers={"Retry-After": "60", "X-RateLimit-Remaining": "0"}
        )
    # Expose remaining rate limit header
    request.state.ratelimit_remaining = remaining
