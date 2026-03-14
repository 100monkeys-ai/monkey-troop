from datetime import datetime, timedelta
from coordinator.domain.verification.models import Challenge, BenchmarkResult


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


def test_calculate_multiplier():
    # Baseline: 35s -> 1.0x
    assert BenchmarkResult.calculate_multiplier(35.0) == 1.0
    # Faster: 17.5s -> 2.0x
    assert BenchmarkResult.calculate_multiplier(17.5) == 2.0
    # Slower: 70.0s -> 0.5x
    assert BenchmarkResult.calculate_multiplier(70.0) == 0.5
    # Cap at 20x: 1.0s -> 20.0x
    assert BenchmarkResult.calculate_multiplier(1.0) == 20.0
    # Zero or negative duration
    assert BenchmarkResult.calculate_multiplier(0) == 0.0
    assert BenchmarkResult.calculate_multiplier(-5) == 0.0
