"""Infrastructure layer implementations for the Inference context."""

import json
from typing import List, Optional

from redis import Redis

from application.inference_ports import NodeDiscoveryRepository
from domain.inference.models import Node


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

    def find_nodes_by_model(self, identifier: str) -> List[Node]:
        nodes = self.list_all_active_nodes()
        if identifier.startswith("sha256:"):
            return [n for n in nodes if any(m.content_hash == identifier for m in n.models)]
        return [n for n in nodes if any(m.name == identifier for m in n.models)]

    def list_all_active_nodes(self) -> List[Node]:
        SCAN_BATCH_SIZE = 100
        cursor = 0
        nodes = []
        while True:
            cursor, keys = self.redis.scan(cursor=cursor, match="node:*", count=SCAN_BATCH_SIZE)

            # Explicitly chunk keys to ensure bounded mget sizes, even if scan returns many keys
            if keys:
                for i in range(0, len(keys), SCAN_BATCH_SIZE):
                    chunk = keys[i : i + SCAN_BATCH_SIZE]
                    raw_nodes = self.redis.mget(chunk)
                    for raw_data in raw_nodes:
                        if raw_data:
                            nodes.append(Node.from_dict(json.loads(raw_data)))

            if cursor == 0:
                break
        return nodes
