import os
import sys
import time
from unittest.mock import MagicMock

# Add coordinator to sys.path
sys.path.append(os.path.join(os.getcwd(), "coordinator"))

from coordinator.application.inference_services import DiscoveryService
from coordinator.domain.inference.models import HardwareSpec, ModelIdentity, Node


def _mi(name: str, content_hash: str = "sha256:default", size_bytes: int = 1000) -> ModelIdentity:
    return ModelIdentity(name=name, content_hash=content_hash, size_bytes=size_bytes)


def _make_node(node_id):
    return Node(
        node_id=node_id,
        tailscale_ip="100.1.1.1",
        status="IDLE",
        models=[_mi("m1")],
        hardware=HardwareSpec("GPU", 1000),
        engines=[],
    )


def benchmark():
    num_nodes = 50
    nodes = [_make_node(f"node_{i}") for i in range(num_nodes)]

    mock_discovery_repo = MagicMock()
    mock_discovery_repo.list_all_active_nodes.return_value = nodes

    mock_reputation_repo = MagicMock()

    # Simulate DB delay
    def slow_get_reputations_batch(node_ids):
        time.sleep(0.01)  # 10ms delay for the WHOLE batch
        return []

    mock_reputation_repo.get_reputations_batch.side_effect = slow_get_reputations_batch

    service = DiscoveryService(mock_discovery_repo, mock_reputation_repo)

    print(f"Benchmarking list_peers with {num_nodes} nodes (OPTIMIZED)...")
    start = time.perf_counter()
    service.list_peers()
    end = time.perf_counter()

    elapsed = end - start
    print(f"Elapsed time: {elapsed:.4f}s")
    print(
        f"Total calls to get_reputations_batch: {mock_reputation_repo.get_reputations_batch.call_count}"
    )


if __name__ == "__main__":
    benchmark()
