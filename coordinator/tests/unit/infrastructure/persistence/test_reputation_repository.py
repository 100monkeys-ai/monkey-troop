"""Integration tests for the SqlAlchemyNodeReputationRepository."""

from datetime import datetime, timezone

import pytest
from domain.inference.reputation import (NodeReputation, ReputationComponents,
                                         ReputationScore)
from infrastructure.persistence.database import Node as DbNode
from infrastructure.persistence.database import User as DbUser
from infrastructure.persistence.reputation_repository import \
    SqlAlchemyNodeReputationRepository


@pytest.fixture
def setup_node(db_session):
    """Create a user and node in the database for FK constraints."""
    user = DbUser(public_key="test_pk_123", balance_seconds=3600)
    db_session.add(user)
    db_session.flush()

    node = DbNode(
        node_id="node_1",
        owner_id=user.id,
        owner_public_key="test_pk_123",
        status="IDLE",
    )
    db_session.add(node)
    db_session.flush()
    return node


@pytest.fixture
def repo(db_session):
    return SqlAlchemyNodeReputationRepository(db_session)


class TestSqlAlchemyNodeReputationRepository:
    def test_get_reputation_returns_none_for_unknown(self, repo):
        assert repo.get_reputation("nonexistent") is None

    def test_record_heartbeat_creates_and_increments(self, repo, setup_node):
        repo.record_heartbeat("node_1")
        rep = repo.get_reputation("node_1")
        assert rep is not None
        assert rep.total_heartbeats_received == 1
        assert rep.node_id == "node_1"

        repo.record_heartbeat("node_1")
        rep = repo.get_reputation("node_1")
        assert rep.total_heartbeats_received == 2

    def test_record_job_outcome_success(self, repo, setup_node):
        repo.record_job_outcome("node_1", success=True)
        rep = repo.get_reputation("node_1")
        assert rep.total_jobs == 1
        assert rep.successful_jobs == 1
        assert rep.failed_jobs == 0

    def test_record_job_outcome_failure(self, repo, setup_node):
        repo.record_job_outcome("node_1", success=False)
        rep = repo.get_reputation("node_1")
        assert rep.total_jobs == 1
        assert rep.successful_jobs == 0
        assert rep.failed_jobs == 1

    def test_save_and_get_round_trip(self, repo, setup_node):
        reputation = NodeReputation(
            node_id="node_1",
            score=ReputationScore(0.85),
            components=ReputationComponents(
                availability=0.9, reliability=0.8, performance=0.85
            ),
            total_jobs=20,
            successful_jobs=18,
            failed_jobs=2,
            total_heartbeats_expected=500,
            total_heartbeats_received=450,
            updated_at=datetime.now(timezone.utc),
        )
        repo.save_reputation(reputation)

        retrieved = repo.get_reputation("node_1")
        assert retrieved is not None
        assert retrieved.score.value == 0.85
        assert retrieved.components.availability == 0.9
        assert retrieved.total_jobs == 20
        assert retrieved.successful_jobs == 18

    def test_get_all_reputations(self, repo, db_session):
        # Create two nodes
        user = DbUser(public_key="pk_multi", balance_seconds=3600)
        db_session.add(user)
        db_session.flush()

        for nid in ["nodeA", "nodeB"]:
            node = DbNode(
                node_id=nid,
                owner_id=user.id,
                owner_public_key="pk_multi",
                status="IDLE",
            )
            db_session.add(node)
        db_session.flush()

        repo.record_heartbeat("nodeA")
        repo.record_heartbeat("nodeB")

        all_reps = repo.get_all_reputations()
        assert len(all_reps) == 2
        node_ids = {r.node_id for r in all_reps}
        assert node_ids == {"nodeA", "nodeB"}
