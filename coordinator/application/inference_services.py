"""Application layer use cases for the Inference context."""

import random
from typing import List, Optional, Dict, Any
from domain.inference.models import Node
from .inference_ports import NodeDiscoveryRepository


class DiscoveryService:
    """Orchestrates node discovery and model registry use cases."""

    def __init__(self, discovery_repo: NodeDiscoveryRepository):
        self.discovery_repo = discovery_repo

    def register_heartbeat(self, node: Node, ttl_seconds: int = 15):
        """Use Case: Update node status and model availability."""
        self.discovery_repo.save_node(node, ttl_seconds)

    def select_node_for_model(self, model_name: str) -> Optional[Node]:
        """Use Case: Find an idle node with a specific model."""
        candidates = self.discovery_repo.find_nodes_by_model(model_name)
        
        # Filter for IDLE status
        idle_candidates = [n for n in candidates if n.status == "IDLE"]
        
        if not idle_candidates:
            return None
            
        # Simple random selection
        return random.choice(idle_candidates)

    def get_aggregated_models(self) -> List[str]:
        """Use Case: List all models currently available in the network."""
        nodes = self.discovery_repo.list_all_active_nodes()
        unique_models = set()
        for node in nodes:
            unique_models.update(node.models)
        return sorted(list(unique_models))

    def list_peers(self, model: Optional[str] = None) -> List[Node]:
        """Use Case: List nodes, optionally filtered by model."""
        if model:
            return self.discovery_repo.find_nodes_by_model(model)
        return self.discovery_repo.list_all_active_nodes()
