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
