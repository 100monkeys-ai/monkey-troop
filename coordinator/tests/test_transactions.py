"""Test credit accounting and transactions."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, User, Node, Transaction
from transactions import (
    create_user_if_not_exists,
    get_user_balance,
    check_sufficient_balance,
    reserve_credits,
    refund_credits,
    record_job_completion,
    generate_receipt_signature,
    STARTER_CREDITS,
)

# Use in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    """Create a fresh database session for each test."""
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def test_new_user_gets_starter_credits(db_session):
    """Test that new users receive starter credits."""
    public_key = "test_user_123"

    user = create_user_if_not_exists(db_session, public_key)

    assert user.public_key == public_key
    assert user.balance_seconds == STARTER_CREDITS


def test_existing_user_not_duplicated(db_session):
    """Test that existing users don't get duplicate starter credits."""
    public_key = "test_user_456"

    user1 = create_user_if_not_exists(db_session, public_key)
    initial_balance = user1.balance_seconds

    user2 = create_user_if_not_exists(db_session, public_key)

    assert user1.id == user2.id
    assert user2.balance_seconds == initial_balance


def test_check_sufficient_balance(db_session):
    """Test balance checking."""
    user = create_user_if_not_exists(db_session, "user_balance_test")

    # Should have enough for 300s job (starter credits = 3600s)
    assert check_sufficient_balance(db_session, user.public_key, 300)

    # Should not have enough for 10000s job
    assert not check_sufficient_balance(db_session, user.public_key, 10000)


def test_reserve_credits(db_session):
    """Test credit reservation."""
    user = create_user_if_not_exists(db_session, "user_reserve_test")
    initial_balance = user.balance_seconds

    # Reserve 300 seconds
    success = reserve_credits(db_session, user.public_key, 300)
    assert success

    # Check balance decreased
    new_balance = get_user_balance(db_session, user.public_key)
    assert new_balance == initial_balance - 300


def test_refund_credits(db_session):
    """Test credit refund."""
    user = create_user_if_not_exists(db_session, "user_refund_test")

    # Reserve then refund
    reserve_credits(db_session, user.public_key, 200)
    balance_after_reserve = get_user_balance(db_session, user.public_key)

    refund_credits(db_session, user.public_key, 100, "test_job_123")
    balance_after_refund = get_user_balance(db_session, user.public_key)

    assert balance_after_refund == balance_after_reserve + 100


def test_job_completion_credit_transfer(db_session):
    """Test full credit transfer workflow."""
    # Create requester and worker
    requester = create_user_if_not_exists(db_session, "requester_abc")
    worker_owner = create_user_if_not_exists(db_session, "worker_owner_xyz")

    # Create worker node
    node = Node(
        node_id="test_node_789",
        owner_id=worker_owner.id,
        multiplier=2.0,
        benchmark_score=15.5,
        trust_score=50,
    )
    db_session.add(node)
    db_session.commit()

    # Reserve credits
    reserve_credits(db_session, requester.public_key, 300)

    # Generate valid signature
    job_id = "job_test_001"
    duration = 250
    signature = generate_receipt_signature(job_id, node.node_id, duration)

    # Record job completion
    result = record_job_completion(
        db_session, job_id, requester.public_key, node.node_id, duration, signature
    )

    assert result["status"] == "success"
    assert result["credits_transferred"] == duration * 2  # 2.0x multiplier

    # Check balances
    db_session.refresh(requester)
    db_session.refresh(worker_owner)
    db_session.refresh(node)

    # Worker should have gained credits
    assert worker_owner.balance_seconds == STARTER_CREDITS + (duration * 2)

    # Node stats should update
    assert node.trust_score > 50  # Increased


def test_invalid_signature_rejected(db_session):
    """Test that invalid HMAC signatures are rejected."""
    requester = create_user_if_not_exists(db_session, "requester_sig_test")
    worker_owner = create_user_if_not_exists(db_session, "worker_sig_test")

    node = Node(node_id="node_sig_test", owner_id=worker_owner.id, multiplier=1.0)
    db_session.add(node)
    db_session.commit()

    # Use invalid signature
    result = record_job_completion(
        db_session,
        "job_invalid_sig",
        requester.public_key,
        node.node_id,
        100,
        "invalid_signature_12345",
    )

    assert result["status"] == "error"
    assert "signature" in result["message"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
