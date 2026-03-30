from domain.inference.models import EngineInfo, HardwareSpec, ModelIdentity, Node
from infrastructure.persistence.inference_repositories import RedisNodeDiscoveryRepository


def _mi(name: str, content_hash: str = "sha256:default", size_bytes: int = 1000) -> ModelIdentity:
    return ModelIdentity(name=name, content_hash=content_hash, size_bytes=size_bytes)


def test_redis_node_discovery_repository_save_and_get(redis_client):
    repo = RedisNodeDiscoveryRepository(redis_client)
    node = Node(
        node_id="node_1",
        tailscale_ip="100.64.0.1",
        status="active",
        models=[
            _mi("llama2", "sha256:aaa", 1000),
            _mi("mistral", "sha256:bbb", 2000),
        ],
        hardware=HardwareSpec(gpu="RTX 4090", vram_free_mb=24000),
        engines=[EngineInfo(type="ollama", version="0.1.0", port=11434)],
    )

    repo.save_node(node, ttl_seconds=60)

    fetched_node = repo.get_node("node_1")
    assert fetched_node is not None
    assert fetched_node.node_id == "node_1"
    assert any(m.name == "llama2" for m in fetched_node.models)
    assert fetched_node.hardware.gpu == "RTX 4090"


def test_redis_node_discovery_repository_get_nonexistent(redis_client):
    repo = RedisNodeDiscoveryRepository(redis_client)
    fetched_node = repo.get_node("nonexistent")
    assert fetched_node is None


def test_redis_node_discovery_repository_find_nodes_by_model_name(redis_client):
    redis_client.flushall()
    repo = RedisNodeDiscoveryRepository(redis_client)
    node1 = Node(
        node_id="node_1",
        tailscale_ip="100.64.0.1",
        status="active",
        models=[_mi("llama2", "sha256:aaa")],
        hardware=HardwareSpec(gpu="RTX 4090", vram_free_mb=24000),
        engines=[],
    )
    node2 = Node(
        node_id="node_2",
        tailscale_ip="100.64.0.2",
        status="active",
        models=[_mi("mistral", "sha256:bbb")],
        hardware=HardwareSpec(gpu="RTX 4090", vram_free_mb=24000),
        engines=[],
    )

    repo.save_node(node1, 60)
    repo.save_node(node2, 60)

    llama_nodes = repo.find_nodes_by_model("llama2")
    assert len(llama_nodes) == 1
    assert llama_nodes[0].node_id == "node_1"

    mistral_nodes = repo.find_nodes_by_model("mistral")
    assert len(mistral_nodes) == 1
    assert mistral_nodes[0].node_id == "node_2"

    none_nodes = repo.find_nodes_by_model("nonexistent")
    assert len(none_nodes) == 0


def test_redis_node_discovery_repository_find_nodes_by_hash(redis_client):
    redis_client.flushall()
    repo = RedisNodeDiscoveryRepository(redis_client)
    node1 = Node(
        node_id="node_hash_1",
        tailscale_ip="100.64.0.1",
        status="active",
        models=[_mi("llama2", "sha256:abc123")],
        hardware=HardwareSpec(gpu="RTX 4090", vram_free_mb=24000),
        engines=[],
    )
    node2 = Node(
        node_id="node_hash_2",
        tailscale_ip="100.64.0.2",
        status="active",
        models=[_mi("mistral", "sha256:def456")],
        hardware=HardwareSpec(gpu="RTX 4090", vram_free_mb=24000),
        engines=[],
    )

    repo.save_node(node1, 60)
    repo.save_node(node2, 60)

    result = repo.find_nodes_by_model("sha256:abc123")
    assert len(result) == 1
    assert result[0].node_id == "node_hash_1"

    result = repo.find_nodes_by_model("sha256:def456")
    assert len(result) == 1
    assert result[0].node_id == "node_hash_2"

    result = repo.find_nodes_by_model("sha256:nonexistent")
    assert len(result) == 0


def test_redis_node_discovery_repository_list_all_active_nodes_empty(redis_client):
    # clear redis for this test if needed, but it's fake and scoped session
    redis_client.flushall()
    repo = RedisNodeDiscoveryRepository(redis_client)
    nodes = repo.list_all_active_nodes()
    assert nodes == []


def test_redis_node_discovery_repository_list_all_active_nodes_with_data(redis_client):
    redis_client.flushall()
    repo = RedisNodeDiscoveryRepository(redis_client)
    node1 = Node(
        node_id="node_1",
        tailscale_ip="100.64.0.1",
        status="active",
        models=[_mi("llama2", "sha256:aaa")],
        hardware=HardwareSpec(gpu="RTX 4090", vram_free_mb=24000),
        engines=[],
    )
    repo.save_node(node1, 60)

    nodes = repo.list_all_active_nodes()
    assert len(nodes) == 1
    assert nodes[0].node_id == "node_1"
