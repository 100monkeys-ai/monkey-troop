"""Domain models for the Security & Identity context."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Identity:
    """A user's cryptographic identity."""
    public_key: str


@dataclass(frozen=True)
class AuthTicket:
    """A signed authorization ticket for a specific node."""
    token: str
    target_node_id: str
    requester_id: str
    expires_at: datetime
    project: str

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at
