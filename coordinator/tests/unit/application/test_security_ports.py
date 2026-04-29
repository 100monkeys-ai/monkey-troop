from typing import Optional

import pytest

from coordinator.application.security_ports import KeyRepository, TokenService
from coordinator.domain.security.models import AuthTicket


class ConcreteTokenService(TokenService):
    def generate_ticket(
        self, user_id: str, target_node_id: str, project: str = "free-tier"
    ) -> AuthTicket:
        return AuthTicket("token", target_node_id, user_id, None, project)

    def verify_ticket(self, token: str) -> Optional[AuthTicket]:
        return None


class ConcreteKeyRepository(KeyRepository):
    def get_public_key(self) -> str:
        return "pub"

    def get_private_key(self) -> bytes:
        return b"priv"

    def ensure_keys_exist(self) -> None:
        pass


def test_token_service_instantiation():
    with pytest.raises(TypeError) as exc_info:
        TokenService()
    assert "Can't instantiate abstract class TokenService" in str(exc_info.value)
    assert "without an implementation for abstract methods" in str(exc_info.value)


def test_concrete_token_service():
    service = ConcreteTokenService()
    assert isinstance(service, TokenService)
    assert service.generate_ticket("user", "node").token == "token"
    assert service.verify_ticket("token") is None


def test_key_repository_instantiation():
    with pytest.raises(TypeError) as exc_info:
        KeyRepository()
    assert "Can't instantiate abstract class KeyRepository" in str(exc_info.value)
    assert "without an implementation for abstract methods" in str(exc_info.value)


def test_concrete_key_repository():
    repo = ConcreteKeyRepository()
    assert isinstance(repo, KeyRepository)
    assert repo.get_public_key() == "pub"
    assert repo.get_private_key() == b"priv"
    repo.ensure_keys_exist()


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
