"""Infrastructure layer implementations for the Inference context."""

import json
from typing import List, Optional
from redis import Redis
from domain.inference.models import Node
from application.inference_ports import NodeDiscoveryRepository


class RedisNodeDiscoveryRepository(NodeDiscoveryRepository):
    """Redis implementation of the NodeDiscoveryRepository."""

    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    def save_node(self, node: Node, ttl_seconds: int) -> None:
        key = f"node:{node.node_id}"
        self.redis.set(key, node.to_json())
        self.redis.expire(key, ttl_seconds)

    def get_node(self, node_id: str) -> Optional[Node]:
        key = f"node:{node_id}"
        raw_data = self.redis.get(key)
        if not raw_data:
            return None
        return Node.from_dict(json.loads(raw_data))

    def find_nodes_by_model(self, model_name: str) -> List[Node]:
        nodes = self.list_all_active_nodes()
        return [n for n in nodes if model_name in n.models]

    def list_all_active_nodes(self) -> List[Node]:
        keys = list(self.redis.scan_iter("node:*"))
        if not keys:
            return []

        raw_nodes = self.redis.mget(keys)
        nodes = []
        for raw_data in raw_nodes:
            if raw_data:
                nodes.append(Node.from_dict(json.loads(raw_data)))
        return nodes
