import pytest
from coordinator.application.security_ports import KeyRepository, TokenService

def test_key_repository_requires_ensure_keys_exist():
    class IncompleteKeyRepository(KeyRepository):
        def get_public_key(self) -> str:
            return "public_key"

        def get_private_key(self) -> bytes:
            return b"private_key"

    with pytest.raises(TypeError, match="Can't instantiate abstract class IncompleteKeyRepository"):
        IncompleteKeyRepository()

def test_key_repository_all_methods_implemented():
    class CompleteKeyRepository(KeyRepository):
        def get_public_key(self) -> str:
            return "public_key"

        def get_private_key(self) -> bytes:
            return b"private_key"

        def ensure_keys_exist(self) -> None:
            pass

    repo = CompleteKeyRepository()
    assert isinstance(repo, KeyRepository)

def test_token_service_requires_all_methods():
    class IncompleteTokenService(TokenService):
        def generate_ticket(self, user_id: str, target_node_id: str, project: str = "free-tier"):
            pass

    with pytest.raises(TypeError, match="Can't instantiate abstract class IncompleteTokenService"):
        IncompleteTokenService()

def test_token_service_all_methods_implemented():
    class CompleteTokenService(TokenService):
        def generate_ticket(self, user_id: str, target_node_id: str, project: str = "free-tier"):
            pass

        def verify_ticket(self, token: str):
            pass

    service = CompleteTokenService()
    assert isinstance(service, TokenService)
