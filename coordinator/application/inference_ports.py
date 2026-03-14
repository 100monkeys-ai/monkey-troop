"""Application layer ports for the Inference context."""

from abc import ABC, abstractmethod
from typing import List, Optional

from domain.inference.models import Node


class NodeDiscoveryRepository(ABC):
    """Port for persistence and discovery of active nodes (e.g. Redis)."""

    @abstractmethod
    def save_node(self, node: Node, ttl_seconds: int) -> None:
        pass

    @abstractmethod
    def get_node(self, node_id: str) -> Optional[Node]:
        pass

    @abstractmethod
    def find_nodes_by_model(self, model_name: str) -> List[Node]:
        pass

    @abstractmethod
    def list_all_active_nodes(self) -> List[Node]:
        pass
