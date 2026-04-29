"""Infrastructure layer implementations of the Accounting context repositories."""

from typing import List, Optional

from application.accounting_ports import TransactionRepository, UserRepository
from domain.accounting.models import CreditAmount, Transaction, User
from sqlalchemy.orm import Session

from . import database as db_models


class SqlAlchemyUserRepository(UserRepository):
    """SqlAlchemy implementation of the UserRepository."""

    def __init__(self, session: Session):
        self.session = session

    def get_by_public_key(self, public_key: str) -> Optional[User]:
        db_user = (
            self.session.query(db_models.User)
            .filter(db_models.User.public_key == public_key)
            .first()
        )
        if not db_user:
            return None

        return User(
            id=db_user.id,
            public_key=db_user.public_key,
            balance=CreditAmount(db_user.balance_seconds),
            created_at=db_user.created_at,
        )

    def save(self, user: User) -> None:
        db_user = (
            self.session.query(db_models.User)
            .filter(db_models.User.public_key == user.public_key)
            .first()
        )

        if not db_user:
            db_user = db_models.User(
                public_key=user.public_key,
                balance_seconds=user.balance.seconds,
                created_at=user.created_at,
            )
            self.session.add(db_user)
        else:
            db_user.balance_seconds = user.balance.seconds

        self.session.commit()


class SqlAlchemyTransactionRepository(TransactionRepository):
    """SqlAlchemy implementation of the TransactionRepository."""

    def __init__(self, session: Session):
        self.session = session

    def record_transaction(self, transaction: Transaction) -> None:
        db_txn = db_models.Transaction(
            job_id=transaction.job_id,
            from_user=transaction.from_user,
            to_user=transaction.to_user,
            duration_seconds=0,  # Legacy field, needs review
            credits_transferred=transaction.amount.seconds,
            timestamp=transaction.timestamp,
        )
        self.session.add(db_txn)
        self.session.commit()

    def get_history_by_user(
        self, public_key: str, limit: int = 50
    ) -> List[Transaction]:
        db_txns = (
            self.session.query(db_models.Transaction)
            .filter(
                (db_models.Transaction.from_user == public_key)
                | (db_models.Transaction.to_user == public_key)
            )
            .order_by(db_models.Transaction.timestamp.desc())
            .limit(limit)
            .all()
        )

        return [
            Transaction(
                id=txn.id,
                job_id=txn.job_id,
                from_user=txn.from_user,
                to_user=txn.to_user,
                amount=CreditAmount(int(txn.credits_transferred)),
                timestamp=txn.timestamp,
                type="transaction",  # Simplified
            )
            for txn in db_txns
        ]
