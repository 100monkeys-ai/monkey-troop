"""Integration tests for Monkey Troop end-to-end flow."""

import json
import time
import httpx
import pytest
from main import app, startup_event
from database import get_db
from dependencies import get_redis_client

# Test configuration
COORDINATOR_URL = "http://localhost:8000"
TEST_USER_KEY = "test_user_12345"
TEST_MODEL = "llama2:7b"


@pytest.fixture
async def coordinator_client(db_session, redis_client):
    """HTTP client for coordinator with overridden database and redis."""

    # Override get_db to use the test session
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_redis():
        return redis_client

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_client] = override_get_redis

    # Ensure keys and base setup
    await startup_event()

    # httpx 0.28+ uses transport for app
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", timeout=30.0
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_check(coordinator_client):
    """Test coordinator health endpoint."""
    response = await coordinator_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_public_key_endpoint(coordinator_client):
    """Test RSA public key distribution."""
    response = await coordinator_client.get("/public-key")
    assert response.status_code == 200
    data = response.json()
    assert "public_key" in data
    pem = data["public_key"]
    assert "BEGIN PUBLIC KEY" in pem
    assert "END PUBLIC KEY" in pem


@pytest.mark.asyncio
async def test_starter_credits_on_first_auth(coordinator_client):
    """Test that new users receive starter credits."""
    test_user = f"test_user_{int(time.time())}"

    # Get balance (creates user)
    response = await coordinator_client.get(f"/users/{test_user}/balance")
    assert response.status_code == 200
    data = response.json()
    assert data["balance_seconds"] == 3600


@pytest.mark.asyncio
async def test_no_nodes_available_returns_503(coordinator_client, redis_client):
    """Test graceful degradation when no workers available."""
    # Ensure no nodes for this model
    keys = redis_client.keys("node:*")
    if keys:
        redis_client.delete(*keys)

    response = await coordinator_client.post(
        "/authorize", json={"model": TEST_MODEL, "requester": TEST_USER_KEY}
    )

    assert response.status_code == 503
    assert "No idle nodes found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_transaction_history(coordinator_client):
    """Test transaction history endpoint."""
    response = await coordinator_client.get(
        f"/users/{TEST_USER_KEY}/transactions", params={"limit": 10}
    )

    assert response.status_code == 200
    data = response.json()
    assert "transactions" in data
    assert isinstance(data["transactions"], list)


@pytest.mark.asyncio
async def test_jwt_structure(coordinator_client, redis_client):
    """Test that JWT tokens are issued with correct structure."""
    # Register a fake node
    node_id = "test_node_integration"
    node_data = {
        "node_id": node_id,
        "tailscale_ip": "100.64.0.1",
        "status": "IDLE",
        "models": [TEST_MODEL],
        "hardware": {"gpu": "Test GPU", "vram_free": 8192},
        "engines": [{"type": "ollama", "version": "0.1.0", "port": 11434}],
    }

    redis_client.setex(f"node:{node_id}", 60, json.dumps(node_data))

    # Try authorization
    response = await coordinator_client.post(
        "/authorize", json={"model": TEST_MODEL, "requester": TEST_USER_KEY}
    )

    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert "target_ip" in data

    token = data["token"]
    parts = token.split(".")
    assert len(parts) == 3
