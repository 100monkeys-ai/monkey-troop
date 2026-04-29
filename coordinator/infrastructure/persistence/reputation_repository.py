"""Infrastructure layer implementation for the Node Reputation repository."""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from application.inference_ports import NodeReputationRepository
from domain.inference.reputation import (
    NodeReputation,
    ReputationComponents,
    ReputationScore,
)

from . import database as db_models


class SqlAlchemyNodeReputationRepository(NodeReputationRepository):
    """PostgreSQL implementation of the NodeReputationRepository."""

    def __init__(self, session: Session):
        self.session = session

    def get_reputation(self, node_id: str) -> Optional[NodeReputation]:
        db_rep = (
            self.session.query(db_models.NodeReputationModel)
            .filter(db_models.NodeReputationModel.node_id == node_id)
            .first()
        )
        if not db_rep:
            return None
        return self._to_domain(db_rep)

    def get_reputations_batch(self, node_ids: List[str]) -> List[NodeReputation]:
        db_reps = (
            self.session.query(db_models.NodeReputationModel)
            .filter(db_models.NodeReputationModel.node_id.in_(node_ids))
            .all()
        )
        return [self._to_domain(r) for r in db_reps]

    def save_reputation(self, reputation: NodeReputation) -> None:
        db_rep = (
            self.session.query(db_models.NodeReputationModel)
            .filter(db_models.NodeReputationModel.node_id == reputation.node_id)
            .first()
        )
        if not db_rep:
            db_rep = db_models.NodeReputationModel(node_id=reputation.node_id)
            self.session.add(db_rep)

        db_rep.score = reputation.score.value
        db_rep.availability = reputation.components.availability
        db_rep.reliability = reputation.components.reliability
        db_rep.performance = reputation.components.performance
        db_rep.total_jobs = reputation.total_jobs
        db_rep.successful_jobs = reputation.successful_jobs
        db_rep.failed_jobs = reputation.failed_jobs
        db_rep.total_heartbeats_expected = reputation.total_heartbeats_expected
        db_rep.total_heartbeats_received = reputation.total_heartbeats_received
        db_rep.updated_at = reputation.updated_at
        self.session.commit()

    def get_all_reputations(self) -> List[NodeReputation]:
        db_reps = self.session.query(db_models.NodeReputationModel).all()
        return [self._to_domain(r) for r in db_reps]

    def record_job_outcome(self, node_id: str, success: bool) -> None:
        db_rep = self._get_or_create(node_id)
        db_rep.total_jobs += 1
        if success:
            db_rep.successful_jobs += 1
        else:
            db_rep.failed_jobs += 1
        db_rep.updated_at = datetime.now(timezone.utc)
        self.session.commit()

    def record_heartbeat(self, node_id: str) -> None:
        db_rep = self._get_or_create(node_id)
        db_rep.total_heartbeats_received += 1
        db_rep.updated_at = datetime.now(timezone.utc)
        self.session.commit()

    def _get_or_create(self, node_id: str) -> db_models.NodeReputationModel:
        db_rep = (
            self.session.query(db_models.NodeReputationModel)
            .filter(db_models.NodeReputationModel.node_id == node_id)
            .first()
        )
        if not db_rep:
            db_rep = db_models.NodeReputationModel(
                node_id=node_id,
                score=0.5,
                availability=1.0,
                reliability=1.0,
                performance=1.0,
                total_jobs=0,
                successful_jobs=0,
                failed_jobs=0,
                total_heartbeats_expected=0,
                total_heartbeats_received=0,
                updated_at=datetime.now(timezone.utc),
            )
            self.session.add(db_rep)
            self.session.commit()
        return db_rep

    def _to_domain(self, db_rep: db_models.NodeReputationModel) -> NodeReputation:
        return NodeReputation(
            node_id=db_rep.node_id,
            score=ReputationScore(db_rep.score),
            components=ReputationComponents(
                availability=db_rep.availability,
                reliability=db_rep.reliability,
                performance=db_rep.performance,
            ),
            total_jobs=db_rep.total_jobs,
            successful_jobs=db_rep.successful_jobs,
            failed_jobs=db_rep.failed_jobs,
            total_heartbeats_expected=db_rep.total_heartbeats_expected,
            total_heartbeats_received=db_rep.total_heartbeats_received,
            updated_at=db_rep.updated_at,
        )
