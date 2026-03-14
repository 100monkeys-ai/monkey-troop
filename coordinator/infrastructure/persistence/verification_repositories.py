"""Infrastructure layer implementations for the Verification context."""

import json
import logging
from typing import Optional
from sqlalchemy.orm import Session
from redis import Redis
from domain.verification.models import Challenge, BenchmarkResult
from application.verification_ports import ChallengeRepository, BenchmarkRepository
import database as db_models

logger = logging.getLogger(__name__)


class RedisChallengeRepository(ChallengeRepository):
    """Redis implementation of the ChallengeRepository."""

    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    def save_challenge(self, challenge: Challenge, ttl_seconds: int) -> None:
        key = f"challenge:{challenge.token}"
        data = {
            "seed": challenge.seed,
            "matrix_size": challenge.matrix_size,
            "created_at": challenge.created_at.isoformat(),
            "node_id": challenge.node_id,
        }
        self.redis.setex(key, ttl_seconds, json.dumps(data))

    def get_challenge(self, token: str) -> Optional[Challenge]:
        key = f"challenge:{token}"
        raw_data = self.redis.get(key)
        if not raw_data:
            return None

        data = json.loads(raw_data)
        from datetime import datetime

        return Challenge(
            token=token,
            seed=data["seed"],
            matrix_size=data["matrix_size"],
            created_at=datetime.fromisoformat(data["created_at"]),
            node_id=data["node_id"],
        )

    def delete_challenge(self, token: str) -> None:
        self.redis.delete(f"challenge:{token}")


class SqlAlchemyBenchmarkRepository(BenchmarkRepository):
    """SqlAlchemy implementation of the BenchmarkRepository."""

    def __init__(self, session: Session):
        self.session = session

    def save_result(self, result: BenchmarkResult) -> None:
        # Check if node exists in DB
        node = (
            self.session.query(db_models.Node)
            .filter(db_models.Node.node_id == result.node_id)
            .first()
        )
        if not node:
            # Fallback for now - in production would require explicit registration
            # We skip creating a node here as it's a cross-context concern
            # that should be handled by an orchestrator or event.
            logger.warning(
                "Benchmark result for unknown node_id '%s' was not saved. "
                "Ensure the node is registered before saving benchmark results.",
                result.node_id,
            )
        else:
            node.multiplier = result.multiplier
            node.benchmark_score = result.duration
            node.hardware_model = result.device_name
            node.last_benchmark = result.timestamp
            self.session.commit()

    def get_last_result(self, node_id: str) -> Optional[BenchmarkResult]:
        node = self.session.query(db_models.Node).filter(db_models.Node.node_id == node_id).first()
        if not node or node.last_benchmark is None:
            return None

        return BenchmarkResult(
            node_id=node.node_id,
            duration=node.benchmark_score,
            device_name=node.hardware_model,
            multiplier=node.multiplier,
            timestamp=node.last_benchmark,
        )
