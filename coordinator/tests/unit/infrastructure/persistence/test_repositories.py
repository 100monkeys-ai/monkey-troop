from datetime import datetime
from domain.accounting.models import User, Transaction, CreditAmount
from infrastructure.persistence.repositories import (
    SqlAlchemyUserRepository,
    SqlAlchemyTransactionRepository,
)


def test_sqlalchemy_user_repository_save_and_get(db_session):
    repo = SqlAlchemyUserRepository(db_session)
    user = User(
        id=None, public_key="test_pubkey", balance=CreditAmount(100), created_at=datetime.utcnow()
    )

    # Save new user
    repo.save(user)

    # Get user
    fetched_user = repo.get_by_public_key("test_pubkey")
    assert fetched_user is not None
    assert fetched_user.public_key == "test_pubkey"
    assert fetched_user.balance.seconds == 100

    # Update balance
    user.balance = CreditAmount(200)
    repo.save(user)

    fetched_user = repo.get_by_public_key("test_pubkey")
    assert fetched_user.balance.seconds == 200


def test_sqlalchemy_user_repository_get_nonexistent(db_session):
    repo = SqlAlchemyUserRepository(db_session)
    fetched_user = repo.get_by_public_key("nonexistent")
    assert fetched_user is None


def test_sqlalchemy_transaction_repository_record_and_get_history(db_session):
    repo = SqlAlchemyTransactionRepository(db_session)
    txn = Transaction(
        id=None,
        job_id="job_1",
        from_user="user_a",
        to_user="user_b",
        amount=CreditAmount(50),
        timestamp=datetime.utcnow(),
        type="transaction",
    )

    repo.record_transaction(txn)

    history = repo.get_history_by_user("user_a")
    assert len(history) == 1
    assert history[0].job_id == "job_1"
    assert history[0].amount.seconds == 50
    assert history[0].from_user == "user_a"
    assert history[0].to_user == "user_b"

    history_to = repo.get_history_by_user("user_b")
    assert len(history_to) == 1
    assert history_to[0].job_id == "job_1"

    history_none = repo.get_history_by_user("user_c")
    assert len(history_none) == 0
