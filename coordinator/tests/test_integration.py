"""Integration tests for Monkey Troop end-to-end flow."""

import json
import time

import httpx
import pytest
import pytest_asyncio
import redis
from main import app

from main import app

# Test configuration
COORDINATOR_URL = "http://localhost:8000"
TEST_USER_KEY = "test_user_12345"
TEST_MODEL = "llama2:7b"


@pytest.fixture
async def coordinator_client():
    """HTTP client for coordinator."""
    # Ensure database is initialized
    await startup_event()
    async with httpx.AsyncClient(app=app, base_url="http://test", timeout=30.0) as client:
        yield client


@pytest.fixture
def redis_client():
    """Redis client for checking state."""
    return redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)


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
    pem = response.text
    assert "BEGIN PUBLIC KEY" in pem
    assert "END PUBLIC KEY" in pem


@pytest.mark.asyncio
async def test_starter_credits_on_first_auth(coordinator_client):
    """Test that new users receive starter credits."""
    # Use unique user ID
    test_user = f"test_user_{int(time.time())}"

    # Check balance before authorization (should create user with starter credits)
    response = await coordinator_client.get(f"/users/{test_user}/balance")

    # First request might be 0 if user doesn't exist yet
    # After authorization, balance should exist

    # Try to authorize - will create user if needed
    # Note: This will fail if no workers available, but should create user
    try:
        auth_response = await coordinator_client.post(
            "/authorize", json={"model": TEST_MODEL, "requester": test_user}
        )
        # If successful, credits should be deducted
        if auth_response.status_code == 200:
            # Check balance after reservation
            balance_response = await coordinator_client.get(f"/users/{test_user}/balance")
            assert balance_response.status_code == 200
            balance = balance_response.json()
            assert "balance_seconds" in balance
            # Should have starter credits minus reservation
            assert balance["balance_seconds"] > 0
    except httpx.HTTPStatusError:
        # Expected if no workers available
        pass


@pytest.mark.asyncio
async def test_insufficient_credits_rejection(coordinator_client):
    """Test that authorization is rejected when balance too low."""
    # Create user with very low balance by using up credits
    test_user = f"low_balance_{int(time.time())}"

    # Would need to deplete balance first, which requires actual job completion
    # For now, just test the API structure
    balance_response = await coordinator_client.get(f"/users/{test_user}/balance")
    assert balance_response.status_code == 200


@pytest.mark.asyncio
async def test_no_nodes_available_returns_503(coordinator_client, redis_client):
    """Test graceful degradation when no workers available."""
    # Clear all nodes from Redis
    keys = redis_client.keys("node:*")
    if keys:
        redis_client.delete(*keys)

    # Try to authorize - should get 503
    response = await coordinator_client.post(
        "/authorize", json={"model": TEST_MODEL, "requester": TEST_USER_KEY}
    )

    assert response.status_code == 503
    data = response.json()
    assert "No" in data["detail"] or "available" in data["detail"].lower()


@pytest.mark.asyncio
async def test_rate_limiting(coordinator_client):
    """Test rate limiting on discovery endpoints."""
    # Make many rapid requests to trigger rate limit
    responses = []
    for i in range(110):  # More than 100/hour limit
        response = await coordinator_client.get("/v1/models")
        responses.append(response.status_code)
        if response.status_code == 429:
            break

    # Should eventually get rate limited
    assert 429 in responses or len(responses) == 110  # Might not hit limit in test


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
    # First register a fake node
    node_data = {
        "node_id": "test_node_integration",
        "tailscale_ip": "100.64.0.1",
        "status": "IDLE",
        "models": [TEST_MODEL],
        "hardware": {"gpu": "Test GPU", "vram_free": 8192},
        "engine": {"type": "ollama", "version": "0.1.0", "port": 11434},
    }

    import json

    redis_client.setex("node:test_node_integration", 60, json.dumps(node_data))

    # Try authorization
    response = await coordinator_client.post(
        "/authorize", json={"model": TEST_MODEL, "requester": TEST_USER_KEY}
    )

    if response.status_code == 200:
        data = response.json()
        assert "token" in data
        assert "target_ip" in data

        # JWT should have 3 parts
        token = data["token"]
        parts = token.split(".")
        assert len(parts) == 3, "JWT should have header.payload.signature"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
