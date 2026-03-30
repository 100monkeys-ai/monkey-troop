"""Application layer ports for the Inference context."""

from abc import ABC, abstractmethod
from typing import List, Optional

from domain.inference.models import Node
from domain.inference.reputation import NodeReputation


class NodeDiscoveryRepository(ABC):
    """Port for persistence and discovery of active nodes (e.g. Redis)."""

    @abstractmethod
    def save_node(self, node: Node, ttl_seconds: int) -> None:
        pass

    @abstractmethod
    def get_node(self, node_id: str) -> Optional[Node]:
        pass

    @abstractmethod
    def find_nodes_by_model(self, identifier: str) -> List[Node]:
        pass

    @abstractmethod
    def list_all_active_nodes(self) -> List[Node]:
        pass


class NodeReputationRepository(ABC):
    """Port for persistence of node reputation data."""

    @abstractmethod
    def get_reputation(self, node_id: str) -> Optional[NodeReputation]:
        pass

    @abstractmethod
    def save_reputation(self, reputation: NodeReputation) -> None:
        pass

    @abstractmethod
    def get_all_reputations(self) -> List[NodeReputation]:
        pass

    @abstractmethod
    def record_job_outcome(self, node_id: str, success: bool) -> None:
        pass

    @abstractmethod
    def record_heartbeat(self, node_id: str) -> None:
        pass
