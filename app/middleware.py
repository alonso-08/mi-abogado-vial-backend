import time
from collections import defaultdict
from fastapi import Request, HTTPException, status


class RateLimiter:
    """Rate limiter simple basado en memoria."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict[str, list[float]] = defaultdict(list)

    def _cleanup(self, key: str) -> None:
        now = time.time()
        self.requests[key] = [
            t for t in self.requests[key] if now - t < self.window_seconds
        ]

    def check(self, key: str) -> bool:
        self._cleanup(key)
        if len(self.requests[key]) >= self.max_requests:
            return False
        self.requests[key].append(time.time())
        return True


login_limiter = RateLimiter(max_requests=5, window_seconds=60)
register_limiter = RateLimiter(max_requests=3, window_seconds=300)
resend_limiter = RateLimiter(max_requests=3, window_seconds=300)


def rate_limit_check(limiter: RateLimiter, key: str) -> None:
    if not limiter.check(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes. Intenta de nuevo mas tarde.",
        )
