from datetime import datetime, timedelta

from infrastructure.security.key_repository import FileSystemKeyRepository
from infrastructure.security.token_service import JoseJwtTokenService
from jose import jwt


def test_jose_jwt_token_service_generate_and_verify(tmp_path):
    keys_dir = tmp_path / "keys"
    key_repo = FileSystemKeyRepository(keys_dir=str(keys_dir))
    token_service = JoseJwtTokenService(key_repo)

    user_id = "test_user"
    target_node = "node_1"
    project = "test_project"

    ticket = token_service.generate_ticket(user_id, target_node, project)

    assert ticket.token is not None
    assert ticket.requester_id == user_id
    assert ticket.target_node_id == target_node
    assert ticket.project == project

    # Verify
    verified_ticket = token_service.verify_ticket(ticket.token)
    assert verified_ticket is not None
    assert verified_ticket.requester_id == user_id
    assert verified_ticket.target_node_id == target_node
    assert verified_ticket.project == project


def test_jose_jwt_token_service_verify_invalid_token(tmp_path):
    keys_dir = tmp_path / "keys"
    key_repo = FileSystemKeyRepository(keys_dir=str(keys_dir))
    token_service = JoseJwtTokenService(key_repo)

    assert token_service.verify_ticket("invalid_token") is None


def test_jose_jwt_token_service_verify_expired_token(tmp_path):
    keys_dir = tmp_path / "keys"
    key_repo = FileSystemKeyRepository(keys_dir=str(keys_dir))
    token_service = JoseJwtTokenService(key_repo)

    # Manually create an expired token
    payload = {
        "sub": "test_user",
        "target_node": "node_1",
        "aud": "swarm-worker",
        "exp": datetime.utcnow() - timedelta(minutes=1),
        "project": "free-tier",
    }
    private_key = key_repo.get_private_key()
    token = jwt.encode(payload, private_key, algorithm="RS256")

    assert token_service.verify_ticket(token) is None
