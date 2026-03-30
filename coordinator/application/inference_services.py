"""Application layer use cases for the Inference context."""

import random
from typing import List, Optional

from domain.inference.models import ModelIdentity, Node

from .inference_ports import NodeDiscoveryRepository


class DiscoveryService:
    """Orchestrates node discovery and model registry use cases."""

    def __init__(self, discovery_repo: NodeDiscoveryRepository):
        self.discovery_repo = discovery_repo

    def register_heartbeat(self, node: Node, ttl_seconds: int = 15):
        """Use Case: Update node status and model availability."""
        self.discovery_repo.save_node(node, ttl_seconds)

    def select_node_for_model(self, identifier: str) -> Optional[Node]:
        """Use Case: Find an idle node with a specific model.

        If identifier starts with 'sha256:', match against content_hash;
        otherwise match against model name.
        """
        candidates = self.discovery_repo.find_nodes_by_model(identifier)

        # Filter for IDLE status
        idle_candidates = [n for n in candidates if n.status == "IDLE"]

        if not idle_candidates:
            return None

        # Simple random selection
        return random.choice(idle_candidates)

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
        """Use Case: List nodes, optionally filtered by model."""
        if model:
            return self.discovery_repo.find_nodes_by_model(model)
        return self.discovery_repo.list_all_active_nodes()
