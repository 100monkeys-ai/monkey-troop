"""Integration tests for rate limiting functionality."""

import pytest

from infrastructure.security.rate_limit import RateLimiter


@pytest.fixture
def limiter(redis_client):
    """Return a RateLimiter instance using the session redis_client fixture."""
    return RateLimiter(redis_client)


def test_reset_limit_integration(limiter, redis_client):
    """Test that reset_limit actually removes the key from the redis store."""
    test_key = "ratelimit:test:reset"

    # Manually set a value in the redis client
    redis_client.set(test_key, "5")
    assert redis_client.get(test_key) == "5"

    # Call reset_limit
    limiter.reset_limit(test_key)

    # Verify the key is deleted
    assert redis_client.get(test_key) is None
