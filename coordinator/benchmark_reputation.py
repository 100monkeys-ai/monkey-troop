import time
import random
from typing import List
from unittest.mock import MagicMock

# Mocking the imports as we might be running this from the root or coordinator dir
import sys
import os

sys.path.append(os.path.join(os.getcwd(), "coordinator"))

from domain.inference.models import Node, ModelIdentity, HardwareSpec
from domain.inference.reputation import NodeReputation, ReputationScore, ReputationComponents
from application.inference_services import DiscoveryService
from application.inference_ports import NodeDiscoveryRepository


def _mi(name: str) -> ModelIdentity:
    return ModelIdentity(name=name, content_hash=f"sha256:{name}", size_bytes=1000)


def _make_node(node_id):
    return Node(
        node_id=node_id,
        tailscale_ip="100.1.1.1",
        status="IDLE",
        models=[_mi("m1")],
        hardware=HardwareSpec("GPU", 1000),
        engines=[],
    )


class LatencyMockReputationRepo:
    def __init__(self, latency=0.01):
        self.latency = latency
        self.reputations = {}

    def get_reputation(self, node_id: str):
        time.sleep(self.latency)
        return self.reputations.get(node_id)

    def get_reputations_batch(self, node_ids: List[str]):
        # This will be implemented later, for now we just sleep once
        time.sleep(self.latency)
        return [self.reputations.get(nid) for nid in node_ids]

    def record_job_outcome(self, node_id, success):
        pass

    def record_heartbeat(self, node_id):
        pass

    def save_reputation(self, rep):
        pass

    def get_all_reputations(self):
        return list(self.reputations.values())


def run_benchmark(num_nodes=50, latency=0.005):
    print(f"Benchmarking with {num_nodes} nodes and {latency*1000:.1f}ms latency per query")

    nodes = [_make_node(f"node_{i}") for i in range(num_nodes)]

    mock_discovery_repo = MagicMock(spec=NodeDiscoveryRepository)
    mock_discovery_repo.list_all_active_nodes.return_value = nodes
    mock_discovery_repo.find_nodes_by_model.return_value = nodes

    latency_repo = LatencyMockReputationRepo(latency=latency)
    for i in range(num_nodes):
        node_id = f"node_{i}"
        latency_repo.reputations[node_id] = NodeReputation(
            node_id=node_id,
            score=ReputationScore(random.random()),
            components=ReputationComponents(1.0, 1.0, 1.0),
            total_jobs=10,
            successful_jobs=10,
            failed_jobs=0,
            total_heartbeats_expected=100,
            total_heartbeats_received=100,
            updated_at=MagicMock(),
        )

    service = DiscoveryService(mock_discovery_repo, latency_repo)

    # Benchmark list_peers
    start = time.perf_counter()
    service.list_peers()
    list_peers_time = time.perf_counter() - start
    print(f"list_peers took: {list_peers_time:.4f}s")

    # Benchmark select_node_for_model
    start = time.perf_counter()
    service.select_node_for_model("m1")
    select_node_time = time.perf_counter() - start
    print(f"select_node_for_model took: {select_node_time:.4f}s")

    return list_peers_time, select_node_time


if __name__ == "__main__":
    run_benchmark()
