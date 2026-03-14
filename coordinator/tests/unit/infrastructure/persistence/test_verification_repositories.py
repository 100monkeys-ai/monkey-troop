from datetime import datetime

from domain.verification.models import BenchmarkResult, Challenge
from infrastructure.persistence import database as db_models
from infrastructure.persistence.verification_repositories import (
    RedisChallengeRepository,
    SqlAlchemyBenchmarkRepository,
)


def test_redis_challenge_repository_save_and_get(redis_client):
    repo = RedisChallengeRepository(redis_client)
    challenge = Challenge(
        token="test_token",
        seed="test_seed",
        matrix_size=1024,
        created_at=datetime.utcnow(),
        node_id="node_1",
    )

    repo.save_challenge(challenge, ttl_seconds=60)

    fetched = repo.get_challenge("test_token")
    assert fetched is not None
    assert fetched.token == "test_token"
    assert fetched.seed == "test_seed"
    assert fetched.node_id == "node_1"


def test_redis_challenge_repository_delete(redis_client):
    repo = RedisChallengeRepository(redis_client)
    challenge = Challenge(
        token="test_token",
        seed="test_seed",
        matrix_size=1024,
        created_at=datetime.utcnow(),
        node_id="node_1",
    )
    repo.save_challenge(challenge, 60)
    repo.delete_challenge("test_token")
    assert repo.get_challenge("test_token") is None


def test_redis_challenge_repository_get_nonexistent(redis_client):
    repo = RedisChallengeRepository(redis_client)
    assert repo.get_challenge("nonexistent") is None


def test_sqlalchemy_benchmark_repository_save_and_get(db_session):
    repo = SqlAlchemyBenchmarkRepository(db_session)

    # Pre-create node in DB
    db_node = db_models.Node(
        node_id="node_1",
        owner_id=1,
        owner_public_key="owner_1",
        tailscale_ip="100.64.0.1",
        status="active",
        models="",
        multiplier=1.0,
        benchmark_score=0,
        hardware_model="",
        last_benchmark=datetime.utcnow(),
    )
    db_session.add(db_node)
    db_session.commit()

    result = BenchmarkResult(
        node_id="node_1",
        duration=10.5,
        device_name="RTX 4090",
        multiplier=2.5,
        timestamp=datetime.utcnow(),
    )

    repo.save_result(result)

    last_result = repo.get_last_result("node_1")
    assert last_result is not None
    assert last_result.multiplier == 2.5
    assert last_result.duration == 10.5
    assert last_result.device_name == "RTX 4090"


def test_sqlalchemy_benchmark_repository_save_nonexistent_node(db_session):
    repo = SqlAlchemyBenchmarkRepository(db_session)
    result = BenchmarkResult(
        node_id="nonexistent",
        duration=10.5,
        device_name="RTX 4090",
        multiplier=2.5,
        timestamp=datetime.utcnow(),
    )
    # Should not raise exception, but logs a warning instead of silently doing nothing
    repo.save_result(result)
    assert repo.get_last_result("nonexistent") is None


def test_sqlalchemy_benchmark_repository_get_last_result_none(db_session):
    repo = SqlAlchemyBenchmarkRepository(db_session)
    # Node exists but no multiplier (e.g. initial state)
    db_node = db_models.Node(
        node_id="node_empty",
        owner_id=1,
        owner_public_key="owner_empty",
        tailscale_ip="1.1.1.1",
        multiplier=None,
    )
    db_session.add(db_node)
    db_session.commit()

    assert repo.get_last_result("node_empty") is None
    assert repo.get_last_result("never_heard_of_you") is None
