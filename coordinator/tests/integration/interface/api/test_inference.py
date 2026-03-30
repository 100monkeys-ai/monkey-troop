import pytest
from fastapi.testclient import TestClient

from infrastructure.dependencies import get_redis_client
from main import app


@pytest.fixture
def client(redis_client):
    def override_get_redis():
        return redis_client

    app.dependency_overrides[get_redis_client] = override_get_redis
    return TestClient(app)


def _model_payload(name: str, content_hash: str = "sha256:aaa", size_bytes: int = 1000) -> dict:
    return {"name": name, "content_hash": content_hash, "size_bytes": size_bytes}


def test_receive_heartbeat(client, redis_client):
    payload = {
        "node_id": "node_1",
        "tailscale_ip": "100.64.0.1",
        "status": "active",
        "models": [_model_payload("llama2")],
        "hardware": {"gpu": "RTX 4090", "vram_free": 24000},
        "engines": [{"type": "ollama", "version": "0.1.0", "port": 11434}],
    }
    response = client.post("/heartbeat", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "seen"}

    # Check redis
    assert redis_client.exists("node:node_1")


def test_list_peers(client, redis_client):
    # Setup node in redis
    payload = {
        "node_id": "node_1",
        "tailscale_ip": "100.64.0.1",
        "status": "active",
        "models": [_model_payload("llama2")],
        "hardware": {"gpu": "RTX 4090", "vram_free": 24000},
        "engines": [],
    }
    client.post("/heartbeat", json=payload)

    response = client.get("/peers")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["nodes"][0]["node_id"] == "node_1"

    # Filter by model name
    response = client.get("/peers?model=llama2")
    assert response.status_code == 200
    assert response.json()["count"] == 1

    response = client.get("/peers?model=mistral")
    assert response.status_code == 200
    assert response.json()["count"] == 0


def test_list_models_openai(client, redis_client):
    # Setup node
    payload = {
        "node_id": "node_1",
        "tailscale_ip": "100.64.0.1",
        "status": "active",
        "models": [
            _model_payload("llama2", "sha256:aaa", 1000),
            _model_payload("mistral", "sha256:bbb", 2000),
        ],
        "hardware": {"gpu": "RTX 4090", "vram_free": 24000},
        "engines": [],
    }
    client.post("/heartbeat", json=payload)

    response = client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    model_ids = [m["id"] for m in data["data"]]
    assert "llama2" in model_ids
    assert "mistral" in model_ids
    # Verify content_hash and size_bytes are included
    for m in data["data"]:
        assert "content_hash" in m
        assert "size_bytes" in m
