"""Infrastructure layer implementation for RSA JWT tokens."""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from domain.security.models import AuthTicket
from application.security_ports import TokenService, KeyRepository


class JoseJwtTokenService(TokenService):
    """Jose library implementation of the TokenService."""

    ALGORITHM = "RS256"
    EXPIRATION_MINUTES = 5

    def __init__(self, key_repo: KeyRepository):
        self.key_repo = key_repo

    def generate_ticket(
        self, user_id: str, target_node_id: str, project: str = "free-tier"
    ) -> AuthTicket:
        expires_at = datetime.utcnow() + timedelta(minutes=self.EXPIRATION_MINUTES)

        payload = {
            "sub": user_id,
            "target_node": target_node_id,
            "aud": "swarm-worker",
            "exp": expires_at,
            "project": project,
        }

        private_key = self.key_repo.get_private_key()
        token = jwt.encode(payload, private_key, algorithm=self.ALGORITHM)

        return AuthTicket(
            token=token,
            target_node_id=target_node_id,
            requester_id=user_id,
            expires_at=expires_at,
            project=project,
        )

    def verify_ticket(self, token: str) -> Optional[AuthTicket]:
        try:
            public_key = self.key_repo.get_public_key()
            payload = jwt.decode(
                token, public_key, algorithms=[self.ALGORITHM], audience="swarm-worker"
            )

            return AuthTicket(
                token=token,
                target_node_id=payload["target_node"],
                requester_id=payload["sub"],
                expires_at=datetime.fromtimestamp(payload["exp"]),
                project=payload["project"],
            )
        except JWTError:
            return None
