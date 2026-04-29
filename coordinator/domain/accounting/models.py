"""Domain models and value objects for the Accounting & Credits context."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class TransactionType(str, Enum):
    """Enumeration of valid transaction types."""

    STARTER_GRANT = "starter_grant"
    JOB_COMPLETION = "job_completion"
    REFUND = "refund"


@dataclass(frozen=True)
class JobCompletionParams:
    """Parameters for processing job completion accounting."""

    job_id: str
    requester_pk: str
    worker_node_id: str
    worker_owner_pk: str
    duration_seconds: int
    multiplier: float


@dataclass(frozen=True)
class CreditAmount:
    """Value object representing a credit amount in seconds."""

    seconds: int

    def __post_init__(self):
        if self.seconds < 0:
            raise ValueError("Credit amount cannot be negative")

    def __add__(self, other: "CreditAmount") -> "CreditAmount":
        return CreditAmount(self.seconds + other.seconds)

    def __sub__(self, other: "CreditAmount") -> "CreditAmount":
        if self.seconds < other.seconds:
            raise ValueError("Insufficient credits for subtraction")
        return CreditAmount(self.seconds - other.seconds)


@dataclass
class User:
    """Domain Entity representing a network participant."""

    id: Optional[int]
    public_key: str
    balance: CreditAmount
    created_at: datetime

    @classmethod
    def create_new(cls, public_key: str, starter_credits: int = 3600) -> "User":
        """Factory method for new users."""
        return cls(
            id=None,
            public_key=public_key,
            balance=CreditAmount(starter_credits),
            created_at=datetime.now(timezone.utc),
        )

    def reserve_credits(self, amount: CreditAmount):
        """Domain logic to reserve credits for an upcoming job.

        Raises:
            ValueError: If the user has insufficient credits for the reservation.
        """
        self.balance = self.balance - amount

    def add_credits(self, amount: CreditAmount):
        """Domain logic to add credits to the user's balance."""
        self.balance = self.balance + amount


@dataclass(frozen=True)
class Transaction:
    """Domain Event/Entity representing a credit movement."""

    id: Optional[int]
    job_id: Optional[str]
    from_user: Optional[str]  # Public Key
    to_user: Optional[str]  # Public Key
    amount: CreditAmount
    timestamp: datetime
    type: TransactionType
