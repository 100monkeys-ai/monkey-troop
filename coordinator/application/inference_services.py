"""Application layer use cases for the Inference context."""

import random
from datetime import datetime, timezone
from typing import List, Optional

from domain.inference.models import ModelIdentity, Node
from domain.inference.reputation import (
    NodeReputation,
    ReputationCalculator,
    ReputationScore,
    ReputationTier,
)

from .inference_ports import NodeDiscoveryRepository, NodeReputationRepository


class DiscoveryService:
    """Orchestrates node discovery and model registry use cases."""

    def __init__(
        self,
        discovery_repo: NodeDiscoveryRepository,
        reputation_repo: NodeReputationRepository,
    ):
        self.discovery_repo = discovery_repo
        self.reputation_repo = reputation_repo

    def register_heartbeat(self, node: Node, ttl_seconds: int = 15):
        """Use Case: Update node status and model availability."""
        self.discovery_repo.save_node(node, ttl_seconds)
        self.reputation_repo.record_heartbeat(node.node_id)

    def select_node_for_model(self, identifier: str) -> Optional[Node]:
        """Use Case: Find an idle node using reputation-weighted selection.

        If identifier starts with 'sha256:', match against content_hash;
        otherwise match against model name.
        """
        candidates = self.discovery_repo.find_nodes_by_model(identifier)
        idle_candidates = [n for n in candidates if n.status == "IDLE"]

        if not idle_candidates:
            return None

        return self._weighted_select(idle_candidates)

    def _weighted_select(self, candidates: List[Node]) -> Optional[Node]:
        """Select a node using reputation-weighted random selection."""
        node_ids = [n.node_id for n in candidates]
        reputations = {r.node_id: r for r in self.reputation_repo.get_reputations_batch(node_ids)}

        weights = []
        for node in candidates:
            rep = reputations.get(node.node_id)
            score = rep.score.value if rep else 0.5
            tier = ReputationTier.from_score(ReputationScore(score))
            if tier == ReputationTier.SUSPENDED:
                weights.append(0.0)
            else:
                weights.append(score**2)

        if sum(weights) == 0:
            return None

        return random.choices(candidates, weights=weights, k=1)[0]

    def get_aggregated_models(self) -> List[ModelIdentity]:
        """Use Case: List all models currently available in the network, deduplicated by content_hash."""
        nodes = self.discovery_repo.list_all_active_nodes()
        seen_hashes: dict[str, ModelIdentity] = {}
        for node in nodes:
            for model in node.models:
                if model.content_hash not in seen_hashes:
                    seen_hashes[model.content_hash] = model
        return sorted(seen_hashes.values(), key=lambda m: m.name)

    def list_peers(self, model: Optional[str] = None) -> List[Node]:
        """Use Case: List nodes, optionally filtered by model, sorted by reputation."""
        if model:
            nodes = self.discovery_repo.find_nodes_by_model(model)
        else:
            nodes = self.discovery_repo.list_all_active_nodes()

        return self._sort_by_reputation(nodes)

    def _sort_by_reputation(self, nodes: List[Node]) -> List[Node]:
        """Sort nodes by reputation score descending."""
        node_ids = [n.node_id for n in nodes]
        reputations = {r.node_id: r for r in self.reputation_repo.get_reputations_batch(node_ids)}

        def get_score(node: Node) -> float:
            rep = reputations.get(node.node_id)
            return rep.score.value if rep else 0.5

        return sorted(nodes, key=get_score, reverse=True)

    def record_job_outcome(self, node_id: str, success: bool):
        """Use Case: Record the outcome of a job for reputation tracking."""
        self.reputation_repo.record_job_outcome(node_id, success)

    def recalculate_reputation(self, node_id: str) -> Optional[NodeReputation]:
        """Use Case: Recalculate a node's reputation score from its metrics."""
        rep = self.reputation_repo.get_reputation(node_id)
        if not rep:
            return None

        score, components = ReputationCalculator.calculate(
            heartbeats_received=rep.total_heartbeats_received,
            heartbeats_expected=rep.total_heartbeats_expected,
            successful_jobs=rep.successful_jobs,
            failed_jobs=rep.failed_jobs,
            avg_throughput_ratio=1.0,
        )

        updated = NodeReputation(
            node_id=rep.node_id,
            score=score,
            components=components,
            total_jobs=rep.total_jobs,
            successful_jobs=rep.successful_jobs,
            failed_jobs=rep.failed_jobs,
            total_heartbeats_expected=rep.total_heartbeats_expected,
            total_heartbeats_received=rep.total_heartbeats_received,
            updated_at=datetime.now(timezone.utc),
        )
        self.reputation_repo.save_reputation(updated)
        return updated
