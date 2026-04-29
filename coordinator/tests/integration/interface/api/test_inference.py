from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from application.inference_services import DiscoveryService
from domain.inference.reputation import (NodeReputation, ReputationComponents,
                                         ReputationScore)
from fastapi.testclient import TestClient
from infrastructure.dependencies import get_discovery_service, get_redis_client
from infrastructure.persistence.inference_repositories import \
    RedisNodeDiscoveryRepository
from main import app


@pytest.fixture
def mock_reputation_repo():
    repo = MagicMock()
    repo.get_reputation.return_value = None
    repo.record_heartbeat.return_value = None
    return repo


@pytest.fixture
def client(redis_client, mock_reputation_repo):
    def override_get_redis():
        return redis_client

    def override_get_discovery():
        return DiscoveryService(
            RedisNodeDiscoveryRepository(redis_client),
            mock_reputation_repo,
        )

    app.dependency_overrides[get_redis_client] = override_get_redis
    app.dependency_overrides[get_discovery_service] = override_get_discovery
    yield TestClient(app)
    app.dependency_overrides.clear()


def _model_payload(
    name: str, content_hash: str = "sha256:aaa", size_bytes: int = 1000
) -> dict:
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
    assert redis_client.exists("node:node_1")


def test_list_peers(client, redis_client):
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
    assert "reputation_score" in data["nodes"][0]

    # Filter by model name
    response = client.get("/peers?model=llama2")
    assert response.status_code == 200
    assert response.json()["count"] == 1

    response = client.get("/peers?model=mistral")
    assert response.status_code == 200
    assert response.json()["count"] == 0


def test_list_models_openai(client, redis_client):
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


def test_node_reputation_endpoint_not_found(client):
    response = client.get("/nodes/nonexistent/reputation")
    assert response.status_code == 404


def test_node_reputation_endpoint(client, mock_reputation_repo):
    mock_reputation_repo.get_reputation.return_value = NodeReputation(
        node_id="node_1",
        score=ReputationScore(0.85),
        components=ReputationComponents(
            availability=0.9, reliability=0.8, performance=0.85
        ),
        total_jobs=20,
        successful_jobs=18,
        failed_jobs=2,
        total_heartbeats_expected=500,
        total_heartbeats_received=450,
        updated_at=datetime(2026, 3, 29, tzinfo=timezone.utc),
    )

    response = client.get("/nodes/node_1/reputation")
    assert response.status_code == 200
    data = response.json()
    assert data["node_id"] == "node_1"
    assert data["score"] == 0.85
    assert data["tier"] == "trusted"
    assert data["components"]["availability"] == 0.9
    assert data["total_jobs"] == 20
    assert data["successful_jobs"] == 18
    assert data["failed_jobs"] == 2
