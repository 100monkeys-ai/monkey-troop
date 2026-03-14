"""Integration tests for orchestrated endpoints in main.py."""

import json

import pytest
from fastapi.testclient import TestClient

from infrastructure.dependencies import get_redis_client
from infrastructure.persistence.database import get_db
from main import app


@pytest.fixture
def client(db_session, redis_client):
    """Return a TestClient with overridden dependencies."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_redis():
        return redis_client

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_client] = override_get_redis

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def test_authorize_request_success(client, redis_client):
    """Test successful authorization flow."""
    # 1. Setup an idle node in Redis
    node_id = "test_node_main"
    model_name = "llama2"
    node_data = {
        "node_id": node_id,
        "tailscale_ip": "100.64.0.5",
        "status": "IDLE",
        "models": [model_name],
        "hardware": {"gpu": "RTX 4090", "vram_free": 24576},
        "engines": [{"type": "ollama", "version": "0.1.0", "port": 11434}],
    }
    redis_client.setex(f"node:{node_id}", 60, json.dumps(node_data))

    # 2. Call authorize
    response = client.post("/authorize", json={"model": model_name, "requester": "user_main_test"})

    assert response.status_code == 200
    data = response.json()
    assert data["target_ip"] == "100.64.0.5"
    assert "token" in data
    assert data["estimated_cost"] == 300


def test_authorize_request_no_node(client, redis_client):
    """Test authorization fails when no nodes are available."""
    # Ensure redis is empty for this model
    keys = redis_client.keys("node:*")
    if keys:
        redis_client.delete(*keys)

    response = client.post(
        "/authorize", json={"model": "non_existent_model", "requester": "user_main_test"}
    )

    assert response.status_code == 503
    assert "No idle nodes found" in response.json()["detail"]


def test_authorize_request_insufficient_credits(client, db_session, redis_client):
    """Test authorization fails when user has low balance."""
    # Setup node
    node_id = "node_credit_test"
    model_name = "llama2"
    node_data = {
        "node_id": node_id,
        "tailscale_ip": "100.64.0.5",
        "status": "IDLE",
        "models": [model_name],
        "hardware": {"gpu": "RTX 4090", "vram_free": 24576},
        "engines": [],
    }
    redis_client.setex(f"node:{node_id}", 60, json.dumps(node_data))

    # Create user with low balance manually in DB
    from infrastructure.persistence.database import User

    user = User(public_key="low_balance_user", balance_seconds=100)
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/authorize", json={"model": model_name, "requester": "low_balance_user"}
    )

    assert response.status_code == 402
    assert "Insufficient credits" in response.json()["detail"]
