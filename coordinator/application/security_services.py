"""Application layer use cases for the Security context."""

from typing import Optional
from domain.security.models import AuthTicket
from .security_ports import TokenService, KeyRepository


class SecurityService:
    """Orchestrates security and identity use cases."""

    def __init__(self, token_service: TokenService, key_repo: KeyRepository):
        self.token_service = token_service
        self.key_repo = key_repo

    def issue_authorization_ticket(self, user_id: str, node_id: str, project: str = "free-tier") -> AuthTicket:
        """Use Case: Issue a signed JWT authorization ticket for a P2P request."""
        return self.token_service.generate_ticket(user_id, node_id, project)

    def verify_incoming_ticket(self, token: str) -> Optional[AuthTicket]:
        """Use Case: Verify an incoming JWT ticket."""
        return self.token_service.verify_ticket(token)

    def get_public_key_for_distribution(self) -> str:
        """Use Case: Retrieve the public key for workers to verify JWTs."""
        return self.key_repo.get_public_key()
