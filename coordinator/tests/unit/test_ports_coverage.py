import pytest

from application.accounting_ports import TransactionRepository, UserRepository
from application.inference_ports import NodeDiscoveryRepository
from application.security_ports import KeyRepository, TokenService
from application.verification_ports import BenchmarkRepository, ChallengeRepository


def test_ports_are_abstract():
    """Ensure that port classes remain abstract and cannot be directly instantiated."""
    with pytest.raises(TypeError):
        UserRepository()  # abstract: requires concrete implementations

    with pytest.raises(TypeError):
        TransactionRepository()

    with pytest.raises(TypeError):
        NodeDiscoveryRepository()

    with pytest.raises(TypeError):
        TokenService()

    with pytest.raises(TypeError):
        KeyRepository()

    with pytest.raises(TypeError):
        ChallengeRepository()

    with pytest.raises(TypeError):
        BenchmarkRepository()


def test_user_repository_can_be_implemented():
    """Verify that a concrete implementation of UserRepository can define and use the required methods."""

    class InMemoryUserRepo(UserRepository):
        def __init__(self):
            self._users = {}

        def get_by_public_key(self, pk):
            return self._users.get(pk)

        def save(self, user):
            # assume user has "pk" attribute or is simply a mapping with "pk" key
            pk = getattr(user, "pk", None) if not isinstance(user, dict) else user.get("pk")
            self._users[pk] = user
            return user

    repo = InMemoryUserRepo()
    user = {"pk": "test-key", "name": "Alice"}
    saved = repo.save(user)
    assert saved is user
    assert repo.get_by_public_key("test-key") == user


def test_key_repository_can_be_implemented():
    """Verify that a concrete implementation of KeyRepository can define and use the required methods."""

    class DummyKeyRepo(KeyRepository):
        def get_public_key(self) -> str:
            return "dummy-public-key"

        def get_private_key(self) -> bytes:
            return b"dummy-private-key"

        def ensure_keys_exist(self) -> None:
            pass

    repo = DummyKeyRepo()
    assert repo.get_public_key() == "dummy-public-key"
    assert repo.get_private_key() == b"dummy-private-key"
    assert repo.ensure_keys_exist() is None


def test_security_ports_abstract_methods():
    """Verify that abstract methods in security ports can be called (for coverage of the 'pass' statements)."""

    class DummyTokenService(TokenService):
        def generate_ticket(self, user_id, target_node_id, project="free-tier"):
            return super().generate_ticket(user_id, target_node_id, project)

        def verify_ticket(self, token):
            return super().verify_ticket(token)

    class DummyKeyRepository(KeyRepository):
        def get_public_key(self):
            return super().get_public_key()

        def get_private_key(self):
            return super().get_private_key()

        def ensure_keys_exist(self):
            return super().ensure_keys_exist()

    token_svc = DummyTokenService()
    token_svc.generate_ticket("user", "node")
    token_svc.verify_ticket("token")

    key_repo = DummyKeyRepository()
    key_repo.get_public_key()
    key_repo.get_private_key()
    key_repo.ensure_keys_exist()
