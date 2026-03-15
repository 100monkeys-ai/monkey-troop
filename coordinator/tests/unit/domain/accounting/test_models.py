from datetime import datetime, timezone

import pytest

from coordinator.domain.accounting.models import CreditAmount, Transaction, TransactionType, User


def test_credit_amount_initialization():
    amount = CreditAmount(100)
    assert amount.seconds == 100


def test_credit_amount_negative_fails():
    with pytest.raises(ValueError, match="Credit amount cannot be negative"):
        CreditAmount(-1)


def test_credit_amount_addition():
    a = CreditAmount(100)
    b = CreditAmount(50)
    c = a + b
    assert c.seconds == 150


def test_credit_amount_subtraction():
    a = CreditAmount(100)
    b = CreditAmount(40)
    c = a - b
    assert c.seconds == 60


def test_credit_amount_subtraction_insufficient_fails():
    a = CreditAmount(50)
    b = CreditAmount(100)
    with pytest.raises(ValueError, match="Insufficient credits for subtraction"):
        _ = a - b


def test_user_create_new():
    public_key = "test_pub_key"
    user = User.create_new(public_key, starter_credits=1000)
    assert user.id is None
    assert user.public_key == public_key
    assert user.balance.seconds == 1000
    assert isinstance(user.created_at, datetime)
    assert user.created_at.tzinfo is not None
    assert user.created_at.tzinfo == timezone.utc


def test_user_reserve_credits():
    user = User.create_new("test_pub_key", starter_credits=1000)
    user.reserve_credits(CreditAmount(400))
    assert user.balance.seconds == 600


def test_user_reserve_credits_insufficient():
    user = User.create_new("test_pub_key", starter_credits=100)
    with pytest.raises(ValueError, match="Insufficient credits for subtraction"):
        user.reserve_credits(CreditAmount(400))


def test_user_add_credits():
    user = User.create_new("test_pub_key", starter_credits=1000)
    user.add_credits(CreditAmount(500))
    assert user.balance.seconds == 1500


def test_transaction_creation():
    now = datetime.now(timezone.utc)
    txn = Transaction(
        id=1,
        job_id="job_123",
        from_user="alice",
        to_user="bob",
        amount=CreditAmount(100),
        timestamp=now,
        type=TransactionType.JOB_COMPLETION,
    )
    assert txn.id == 1
    assert txn.job_id == "job_123"
    assert txn.from_user == "alice"
    assert txn.to_user == "bob"
    assert txn.amount.seconds == 100
    assert txn.type == TransactionType.JOB_COMPLETION
    assert txn.timestamp == now
    assert txn.timestamp.tzinfo is not None
    assert txn.timestamp.utcoffset() is not None
