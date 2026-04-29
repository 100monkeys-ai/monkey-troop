import pytest
from fastapi.testclient import TestClient

from infrastructure.persistence.database import get_db
from main import app


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_get_public_key(client):
    response = client.get("/public-key")
    assert response.status_code == 200
    data = response.json()
    assert "public_key" in data
    assert isinstance(data["public_key"], str)
    assert data["public_key"].startswith("-----BEGIN PUBLIC KEY-----")
    assert "-----END PUBLIC KEY-----" in data["public_key"]
