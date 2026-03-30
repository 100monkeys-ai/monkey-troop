import json

from coordinator.domain.inference.models import EngineInfo, HardwareSpec, ModelIdentity, Node


def test_hardware_spec_initialization():
    hw = HardwareSpec(gpu="RTX 4090", vram_free_mb=24576)
    assert hw.gpu == "RTX 4090"
    assert hw.vram_free_mb == 24576


def test_engine_info_initialization():
    engine = EngineInfo(type="ollama", version="0.1.0", port=11434)
    assert engine.type == "ollama"
    assert engine.version == "0.1.0"
    assert engine.port == 11434


def test_model_identity_initialization():
    mi = ModelIdentity(name="llama2", content_hash="sha256:abc123", size_bytes=4096000)
    assert mi.name == "llama2"
    assert mi.content_hash == "sha256:abc123"
    assert mi.size_bytes == 4096000


def test_model_identity_frozen():
    mi = ModelIdentity(name="llama2", content_hash="sha256:abc123", size_bytes=4096000)
    try:
        mi.name = "other"
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass


def test_model_identity_equality():
    mi1 = ModelIdentity(name="llama2", content_hash="sha256:abc123", size_bytes=4096000)
    mi2 = ModelIdentity(name="llama2", content_hash="sha256:abc123", size_bytes=4096000)
    mi3 = ModelIdentity(name="llama2", content_hash="sha256:def456", size_bytes=4096000)
    assert mi1 == mi2
    assert mi1 != mi3


def test_node_initialization():
    models = [
        ModelIdentity(name="llama2", content_hash="sha256:aaa", size_bytes=1000),
        ModelIdentity(name="mistral", content_hash="sha256:bbb", size_bytes=2000),
    ]
    node = Node(
        node_id="node_1",
        tailscale_ip="100.1.2.3",
        status="IDLE",
        models=models,
        hardware=HardwareSpec(gpu="RTX 3060", vram_free_mb=12288),
        engines=[EngineInfo(type="ollama", version="0.1.0", port=11434)],
    )
    assert node.node_id == "node_1"
    assert node.tailscale_ip == "100.1.2.3"
    assert node.status == "IDLE"
    assert node.models == models
    assert len(node.engines) == 1


def test_node_to_json():
    models = [ModelIdentity(name="llama2", content_hash="sha256:aaa", size_bytes=1000)]
    node = Node(
        node_id="node_1",
        tailscale_ip="100.1.2.3",
        status="IDLE",
        models=models,
        hardware=HardwareSpec(gpu="RTX 3060", vram_free_mb=12000),
        engines=[EngineInfo(type="ollama", version="0.1.0", port=11434)],
    )
    json_str = node.to_json()
    data = json.loads(json_str)
    assert data["node_id"] == "node_1"
    assert data["hardware"]["gpu"] == "RTX 3060"
    assert data["hardware"]["vram_free"] == 12000
    assert data["engines"][0]["type"] == "ollama"
    assert data["models"][0]["name"] == "llama2"
    assert data["models"][0]["content_hash"] == "sha256:aaa"
    assert data["models"][0]["size_bytes"] == 1000


def test_node_from_dict():
    data = {
        "node_id": "node_1",
        "tailscale_ip": "100.1.2.3",
        "status": "BUSY",
        "models": [{"name": "gpt2", "content_hash": "sha256:ccc", "size_bytes": 5000}],
        "hardware": {"gpu": "A100", "vram_free": 40000},
        "engines": [{"type": "vllm", "version": "0.2.0", "port": 8000}],
    }
    node = Node.from_dict(data)
    assert node.node_id == "node_1"
    assert node.status == "BUSY"
    assert node.hardware.gpu == "A100"
    assert node.hardware.vram_free_mb == 40000
    assert len(node.engines) == 1
    assert node.engines[0].type == "vllm"
    assert node.models[0].name == "gpt2"
    assert node.models[0].content_hash == "sha256:ccc"
    assert node.models[0].size_bytes == 5000


def test_node_to_json_from_dict_round_trip():
    models = [
        ModelIdentity(name="llama2", content_hash="sha256:aaa", size_bytes=1000),
        ModelIdentity(name="mistral", content_hash="sha256:bbb", size_bytes=2000),
    ]
    original = Node(
        node_id="node_rt",
        tailscale_ip="100.1.2.3",
        status="IDLE",
        models=models,
        hardware=HardwareSpec(gpu="RTX 3060", vram_free_mb=12000),
        engines=[EngineInfo(type="ollama", version="0.1.0", port=11434)],
    )
    json_str = original.to_json()
    restored = Node.from_dict(json.loads(json_str))
    assert restored.node_id == original.node_id
    assert restored.tailscale_ip == original.tailscale_ip
    assert restored.status == original.status
    assert restored.models == original.models
    assert restored.hardware == original.hardware
    assert restored.engines == original.engines
