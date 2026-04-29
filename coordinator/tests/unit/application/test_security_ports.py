from coordinator.application.security_ports import KeyRepository, TokenService
from coordinator.domain.security.models import AuthTicket
from datetime import datetime


class DummyTokenService(TokenService):
    def generate_ticket(
        self, user_id: str, target_node_id: str, project: str = "free-tier"
    ) -> AuthTicket:
        return AuthTicket("dummy", target_node_id, user_id, datetime.utcnow(), project)

    def verify_ticket(self, token: str) -> AuthTicket | None:
        return None


class DummyKeyRepository(KeyRepository):
    def get_public_key(self) -> str:
        return "dummy_public_key"

    def get_private_key(self) -> bytes:
        return b"dummy_private_key"

    def ensure_keys_exist(self) -> None:
        pass


def test_token_service_port():
    service = DummyTokenService()
    ticket = service.generate_ticket("user", "node")
    assert ticket.token == "dummy"
    assert service.verify_ticket("dummy") is None


def test_key_repository_port():
    repo = DummyKeyRepository()
    assert repo.get_public_key() == "dummy_public_key"
    assert repo.get_private_key() == b"dummy_private_key"
    repo.ensure_keys_exist()  # Should not raise
