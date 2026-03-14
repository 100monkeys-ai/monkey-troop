"""Application layer ports for the Security context."""

from abc import ABC, abstractmethod
from typing import Optional
from domain.security.models import AuthTicket


class TokenService(ABC):
    """Port for generating and verifying auth tokens (e.g. JWT)."""

    @abstractmethod
    def generate_ticket(self, user_id: str, target_node_id: str, project: str = "free-tier") -> AuthTicket:
        pass

    @abstractmethod
    def verify_ticket(self, token: str) -> Optional[AuthTicket]:
        pass


class KeyRepository(ABC):
    """Port for persistence and retrieval of cryptographic keys."""

    @abstractmethod
    def get_public_key(self) -> str:
        pass

    @abstractmethod
    def get_private_key(self) -> bytes:
        pass

    @abstractmethod
    def ensure_keys_exist(self) -> None:
        pass
