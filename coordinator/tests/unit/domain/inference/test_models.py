import json

from coordinator.domain.inference.models import EngineInfo, HardwareSpec, Node


def test_hardware_spec_initialization():
    hw = HardwareSpec(gpu="RTX 4090", vram_free_mb=24576)
    assert hw.gpu == "RTX 4090"
    assert hw.vram_free_mb == 24576


def test_engine_info_initialization():
    engine = EngineInfo(type="ollama", version="0.1.0", port=11434)
    assert engine.type == "ollama"
    assert engine.version == "0.1.0"
    assert engine.port == 11434


def test_node_initialization():
    node = Node(
        node_id="node_1",
        tailscale_ip="100.1.2.3",
        status="IDLE",
        models=["llama2", "mistral"],
        hardware=HardwareSpec(gpu="RTX 3060", vram_free_mb=12288),
        engines=[EngineInfo(type="ollama", version="0.1.0", port=11434)],
    )
    assert node.node_id == "node_1"
    assert node.tailscale_ip == "100.1.2.3"
    assert node.status == "IDLE"
    assert node.models == ["llama2", "mistral"]
    assert len(node.engines) == 1


def test_node_to_json():
    node = Node(
        node_id="node_1",
        tailscale_ip="100.1.2.3",
        status="IDLE",
        models=["llama2"],
        hardware=HardwareSpec(gpu="RTX 3060", vram_free_mb=12000),
        engines=[EngineInfo(type="ollama", version="0.1.0", port=11434)],
    )
    json_str = node.to_json()
    data = json.loads(json_str)
    assert data["node_id"] == "node_1"
    assert data["hardware"]["gpu"] == "RTX 3060"
    assert data["hardware"]["vram_free"] == 12000
    assert data["engines"][0]["type"] == "ollama"


def test_node_from_dict():
    data = {
        "node_id": "node_1",
        "tailscale_ip": "100.1.2.3",
        "status": "BUSY",
        "models": ["gpt2"],
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
