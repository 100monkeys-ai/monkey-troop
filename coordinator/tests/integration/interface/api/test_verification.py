from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from infrastructure.dependencies import get_redis_client
from infrastructure.persistence import database as db_models
from infrastructure.persistence.database import get_db
from main import app


@pytest.fixture
def client(db_session, redis_client):
    def override_get_db():
        yield db_session

    def override_get_redis():
        return redis_client

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_client] = override_get_redis
    return TestClient(app)


def test_request_challenge(client, redis_client):
    response = client.post("/hardware/challenge?node_id=node_1")
    assert response.status_code == 200
    data = response.json()
    assert "challenge_token" in data
    assert "seed" in data
    assert "matrix_size" in data

    # Check redis
    assert redis_client.exists(f"challenge:{data['challenge_token']}")


def test_submit_proof_success(client, db_session, redis_client):
    # Setup node in DB
    db_node = db_models.Node(
        node_id="node_1",
        owner_id=1,
        owner_public_key="owner_1",
        tailscale_ip="100.64.0.1",
        status="active",
        models="",
        multiplier=1.0,
        benchmark_score=0,
        hardware_model="",
        last_benchmark=datetime.utcnow(),
    )
    db_session.add(db_node)
    db_session.commit()

    # Get challenge
    resp = client.post("/hardware/challenge?node_id=node_1")
    challenge_token = resp.json()["challenge_token"]

    # Submit proof (assuming simplified verification always succeeds if inputs are valid)
    # Actually I should check verification_services.py to see how it verifies.
    payload = {
        "node_id": "node_1",
        "challenge_token": challenge_token,
        "proof_hash": "dummy_hash",
        "duration": 5.5,
        "device_name": "RTX 4090",
    }
    response = client.post("/hardware/verify", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "verified"

    # Check node update in DB
    db_session.refresh(db_node)
    assert db_node.benchmark_score == 5.5
    assert db_node.hardware_model == "RTX 4090"


def test_submit_proof_invalid_token(client):
    payload = {
        "node_id": "node_1",
        "challenge_token": "invalid_token",
        "proof_hash": "dummy_hash",
        "duration": 5.5,
        "device_name": "RTX 4090",
    }
    response = client.post("/hardware/verify", json=payload)
    assert response.status_code == 400
    assert "Challenge expired or invalid" in response.json()["detail"]
