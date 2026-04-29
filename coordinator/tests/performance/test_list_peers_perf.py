import time
import json
from coordinator.domain.inference.models import Node, HardwareSpec, EngineInfo, ModelIdentity


def run_benchmark():
    # Create mock nodes
    nodes = []
    for i in range(1000):
        node = Node(
            node_id=f"node_{i}",
            tailscale_ip=f"100.100.100.{i%255}",
            status="IDLE",
            models=[ModelIdentity(name="test-model", content_hash="hash", size_bytes=1000)],
            hardware=HardwareSpec(gpu="A100", vram_free_mb=80000),
            engines=[EngineInfo(type="vllm", version="0.1", port=8000)],
            reputation_score=0.9,
            encryption_public_key="pubkey",
        )
        nodes.append(node)

    # Old way
    start = time.perf_counter()
    nodes_data_old = []
    for n in nodes:
        node_dict = json.loads(n.to_json())
        node_dict["reputation_score"] = n.reputation_score
        nodes_data_old.append(node_dict)
    end = time.perf_counter()
    old_time = end - start

    # New way
    start = time.perf_counter()
    nodes_data_new = []
    for n in nodes:
        node_dict = {
            "node_id": n.node_id,
            "tailscale_ip": n.tailscale_ip,
            "status": n.status,
            "models": [
                {
                    "name": m.name,
                    "content_hash": m.content_hash,
                    "size_bytes": m.size_bytes,
                }
                for m in n.models
            ],
            "hardware": {"gpu": n.hardware.gpu, "vram_free": n.hardware.vram_free_mb},
            "engines": [{"type": e.type, "version": e.version, "port": e.port} for e in n.engines],
            "reputation_score": n.reputation_score,
            "encryption_public_key": n.encryption_public_key,
        }
        nodes_data_new.append(node_dict)
    end = time.perf_counter()
    new_time = end - start

    # Verify correctness
    assert nodes_data_old == nodes_data_new, "Data mismatch"

    print(f"Old time: {old_time:.5f}s")
    print(f"New time: {new_time:.5f}s")
    print(f"Improvement: {old_time / new_time:.2f}x faster")


if __name__ == "__main__":
    run_benchmark()
