from datetime import datetime, timedelta

from coordinator.domain.security.models import AuthTicket, Identity


def test_identity_initialization():
    identity = Identity(public_key="pub_123")
    assert identity.public_key == "pub_123"


def test_auth_ticket_initialization():
    expires_at = datetime.utcnow() + timedelta(hours=1)
    ticket = AuthTicket(
        token="jwt_token",
        target_node_id="node_1",
        requester_id="user_1",
        expires_at=expires_at,
        project="test_proj",
    )
    assert ticket.token == "jwt_token"
    assert ticket.target_node_id == "node_1"
    assert ticket.requester_id == "user_1"
    assert ticket.expires_at == expires_at


def test_auth_ticket_is_expired():
    now = datetime.utcnow()
    not_expired = AuthTicket("t1", "n1", "u1", now + timedelta(seconds=30), "p1")
    expired = AuthTicket("t2", "n2", "u2", now - timedelta(seconds=30), "p2")

    assert not_expired.is_expired() is False
    assert expired.is_expired() is True
