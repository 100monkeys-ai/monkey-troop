from datetime import datetime, timedelta

from coordinator.domain.verification.models import BenchmarkResult, Challenge


def test_challenge_initialization():
    now = datetime.utcnow()
    challenge = Challenge(
        token="token_123", seed="seed_abc", matrix_size=1024, created_at=now, node_id="node_1"
    )
    assert challenge.token == "token_123"
    assert challenge.matrix_size == 1024
    assert challenge.node_id == "node_1"


def test_challenge_is_expired():
    now = datetime.utcnow()
    not_expired = Challenge("t1", "s1", 1024, now - timedelta(seconds=30), "n1")
    expired = Challenge("t2", "s2", 1024, now - timedelta(seconds=90), "n2")

    assert not_expired.is_expired(ttl_seconds=60) is False
    assert expired.is_expired(ttl_seconds=60) is True


def test_benchmark_result_initialization():
    now = datetime.utcnow()
    res = BenchmarkResult(
        node_id="node_1", duration=10.0, device_name="RTX 4090", multiplier=3.5, timestamp=now
    )
    assert res.node_id == "node_1"
    assert res.duration == 10.0
    assert res.multiplier == 3.5


import pytest

@pytest.mark.parametrize(
    "duration,expected_multiplier",
    [
        (35.0, 1.0),      # Baseline
        (17.5, 2.0),      # Faster (2x)
        (70.0, 0.5),      # Slower (0.5x)
        (1.0, 20.0),      # Cap at 20x
        (0.5, 20.0),      # Faster than cap
        (0.0, 1.0),       # Edge case: zero duration
        (-5.0, 1.0),      # Edge case: negative duration
        (350.0, 0.1),     # Very slow
        (3500.0, 0.01),   # Extremely slow
    ],
)
def test_calculate_multiplier(duration, expected_multiplier):
    assert BenchmarkResult.calculate_multiplier(duration) == expected_multiplier
