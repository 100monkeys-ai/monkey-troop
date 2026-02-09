"""Redis-based rate limiting."""

import redis
from typing import Optional
from datetime import datetime

# Rate limit configuration
DISCOVERY_LIMIT = 100  # requests per hour
INFERENCE_LIMIT = 20   # requests per hour
WINDOW_SECONDS = 3600  # 1 hour


class RateLimiter:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    def check_rate_limit(
        self,
        key: str,
        limit: int,
        window: int = WINDOW_SECONDS
    ) -> tuple[bool, int]:
        """
        Check if request is within rate limit.
        
        Returns: (allowed: bool, remaining: int)
        """
        current = self.redis.get(key)
        
        if current is None:
            # First request in window
            self.redis.setex(key, window, 1)
            return (True, limit - 1)
        
        current_count = int(current)
        
        if current_count >= limit:
            return (False, 0)
        
        # Increment counter
        self.redis.incr(key)
        return (True, limit - current_count - 1)
    
    def check_discovery_limit(self, ip_address: str) -> tuple[bool, int]:
        """Check discovery endpoint rate limit (100/hour per IP)."""
        key = f"ratelimit:discovery:{ip_address}"
        return self.check_rate_limit(key, DISCOVERY_LIMIT)
    
    def check_inference_limit(self, user_id: str) -> tuple[bool, int]:
        """Check inference endpoint rate limit (20/hour per user)."""
        key = f"ratelimit:inference:{user_id}"
        return self.check_rate_limit(key, INFERENCE_LIMIT)
    
    def reset_limit(self, key: str):
        """Reset rate limit for a key (admin function)."""
        self.redis.delete(key)
