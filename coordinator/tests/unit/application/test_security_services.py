import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta
from coordinator.application.security_services import SecurityService
from coordinator.domain.security.models import AuthTicket


@pytest.fixture
def mock_token_service():
    return MagicMock()


@pytest.fixture
def mock_key_repo():
    return MagicMock()


@pytest.fixture
def security_service(mock_token_service, mock_key_repo):
    return SecurityService(mock_token_service, mock_key_repo)


def test_issue_authorization_ticket(security_service, mock_token_service):
    user_id = "user_1"
    node_id = "node_1"
    expires_at = datetime.utcnow() + timedelta(hours=1)
    ticket = AuthTicket("token123", node_id, user_id, expires_at, "free-tier")

    mock_token_service.generate_ticket.return_value = ticket

    res = security_service.issue_authorization_ticket(user_id, node_id)
    assert res == ticket
    mock_token_service.generate_ticket.assert_called_once_with(user_id, node_id, "free-tier")


def test_verify_incoming_ticket(security_service, mock_token_service):
    token = "token123"
    ticket = AuthTicket(token, "n1", "u1", datetime.utcnow(), "p1")
    mock_token_service.verify_ticket.return_value = ticket

    res = security_service.verify_incoming_ticket(token)
    assert res == ticket
    mock_token_service.verify_ticket.assert_called_once_with(token)


def test_get_public_key_for_distribution(security_service, mock_key_repo):
    mock_key_repo.get_public_key.return_value = "PEM_PUBLIC_KEY"
    res = security_service.get_public_key_for_distribution()
    assert res == "PEM_PUBLIC_KEY"
    mock_key_repo.get_public_key.assert_called_once()
