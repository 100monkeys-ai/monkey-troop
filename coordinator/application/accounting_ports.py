"""Application layer ports (interfaces) for the Accounting context."""

from abc import ABC, abstractmethod
from typing import List, Optional

from domain.accounting.models import Transaction, User


class UserRepository(ABC):
    """Port for persistence of User domain entities."""

    @abstractmethod
    def get_by_public_key(self, public_key: str) -> Optional[User]:
        pass

    @abstractmethod
    def save(self, user: User) -> None:
        pass


class TransactionRepository(ABC):
    """Port for persistence of Transaction domain entities."""

    @abstractmethod
    def record_transaction(self, transaction: Transaction) -> None:
        pass

    @abstractmethod
    def get_history_by_user(self, public_key: str, limit: int = 50) -> List[Transaction]:
        pass
