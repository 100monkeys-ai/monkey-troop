"""Test rate limiting functionality."""

from unittest.mock import MagicMock

import pytest
from infrastructure.security.rate_limit import (DISCOVERY_LIMIT,
                                                INFERENCE_LIMIT,
                                                WINDOW_SECONDS, RateLimiter)


@pytest.fixture
def mock_redis():
    """Return a mock Redis client."""
    return MagicMock()


@pytest.fixture
def limiter(mock_redis):
    """Return a RateLimiter instance with a mock Redis client."""
    return RateLimiter(mock_redis)


def test_check_rate_limit_first_request(limiter, mock_redis):
    """Test rate limit check for the first request in a window."""
    mock_redis.get.return_value = None

    allowed, remaining = limiter.check_rate_limit("test_key", 5)

    assert allowed is True
    assert remaining == 4
    mock_redis.get.assert_called_once_with("test_key")
    mock_redis.setex.assert_called_once_with("test_key", WINDOW_SECONDS, 1)


def test_check_rate_limit_custom_window(limiter, mock_redis):
    """Test rate limit check uses a custom window value when provided."""
    mock_redis.get.return_value = None

    custom_window = 10
    allowed, remaining = limiter.check_rate_limit("test_key", 5, window=custom_window)

    assert allowed is True
    assert remaining == 4
    mock_redis.get.assert_called_once_with("test_key")
    mock_redis.setex.assert_called_once_with("test_key", custom_window, 1)


def test_check_rate_limit_subsequent_request(limiter, mock_redis):
    """Test rate limit check for a subsequent request within the limit."""
    mock_redis.get.return_value = b"2"

    allowed, remaining = limiter.check_rate_limit("test_key", 5)

    assert allowed is True
    assert remaining == 2
    mock_redis.get.assert_called_once_with("test_key")
    mock_redis.incr.assert_called_once_with("test_key")
    mock_redis.setex.assert_not_called()


def test_check_rate_limit_boundary_last_allowed(limiter, mock_redis):
    """Test rate limit check when processing the last allowed request."""
    mock_redis.get.return_value = b"4"

    allowed, remaining = limiter.check_rate_limit("test_key", 5)

    assert allowed is True
    assert remaining == 0
    mock_redis.get.assert_called_once_with("test_key")
    mock_redis.incr.assert_called_once_with("test_key")
    mock_redis.setex.assert_not_called()


def test_check_rate_limit_exceeded(limiter, mock_redis):
    """Test rate limit check when the limit is exceeded."""
    mock_redis.get.return_value = b"5"

    allowed, remaining = limiter.check_rate_limit("test_key", 5)

    assert allowed is False
    assert remaining == 0
    mock_redis.get.assert_called_once_with("test_key")
    mock_redis.incr.assert_not_called()
    mock_redis.setex.assert_not_called()


def test_check_discovery_limit(limiter):
    """Test discovery limit check uses correct key and limit."""
    limiter.check_rate_limit = MagicMock(return_value=(True, 99))

    allowed, remaining = limiter.check_discovery_limit("1.2.3.4")

    assert allowed is True
    assert remaining == 99
    limiter.check_rate_limit.assert_called_once_with(
        "ratelimit:discovery:1.2.3.4", DISCOVERY_LIMIT
    )


def test_check_inference_limit(limiter):
    """Test inference limit check uses correct key and limit."""
    limiter.check_rate_limit = MagicMock(return_value=(True, 19))

    allowed, remaining = limiter.check_inference_limit("user123")

    assert allowed is True
    assert remaining == 19
    limiter.check_rate_limit.assert_called_once_with(
        "ratelimit:inference:user123", INFERENCE_LIMIT
    )


def test_reset_limit(limiter, mock_redis):
    """Test reset limit deletes the key from Redis."""
    limiter.reset_limit("test_key")

    mock_redis.delete.assert_called_once_with("test_key")
