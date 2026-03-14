import pytest
from fastapi.testclient import TestClient
from main import app
from infrastructure.persistence.database import get_db
from infrastructure.persistence import database as db_models
from datetime import datetime


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_get_balance(client, db_session):
    # User doesn't exist yet, should be created with starter credits (3600)
    response = client.get("/users/test_user/balance")
    assert response.status_code == 200
    data = response.json()
    assert data["public_key"] == "test_user"
    assert data["balance_seconds"] == 3600

    # Check DB
    user = db_session.query(db_models.User).filter(db_models.User.public_key == "test_user").first()
    assert user is not None
    assert user.balance_seconds == 3600


def test_get_transactions(client, db_session):
    # Create some transactions
    txn = db_models.Transaction(
        job_id="job_1",
        from_user="user_a",
        to_user="worker_1",
        duration_seconds=100,
        credits_transferred=100,
        timestamp=datetime.utcnow(),
    )
    db_session.add(txn)
    db_session.commit()

    response = client.get("/users/user_a/transactions")
    assert response.status_code == 200
    data = response.json()
    assert len(data["transactions"]) == 1
    assert data["transactions"][0]["requester"] == "user_a"
    assert data["transactions"][0]["credits"] == 100
