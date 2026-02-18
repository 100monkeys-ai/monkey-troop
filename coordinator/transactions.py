"""Credit accounting and transaction management for Monkey Troop."""

import hmac
import hashlib
import os
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_
from database import User, Node, Transaction
from typing import Optional

# HMAC secret for job receipts - must be shared with workers
RECEIPT_SECRET = os.getenv("RECEIPT_SECRET")
if not RECEIPT_SECRET:
    raise RuntimeError(
        "RECEIPT_SECRET environment variable is not set. This is required for security."
    )

# Starter credits: 1 hour = 3600 seconds
STARTER_CREDITS = 3600


def create_user_if_not_exists(db: Session, public_key: str) -> User:
    """Create user with starter credits if they don't exist."""
    user = db.query(User).filter(User.public_key == public_key).first()

    if not user:
        user = User(
            public_key=public_key,
            balance_seconds=STARTER_CREDITS,
            created_at=datetime.utcnow(),
            last_active=datetime.utcnow(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Record starter credit transaction
        txn = Transaction(
            from_user=None,  # System grant
            to_user=public_key,
            duration_seconds=0,
            credits_transferred=STARTER_CREDITS,
            job_id="starter_grant",
            node_id=None,
            timestamp=datetime.utcnow(),
            metadata={"type": "starter_grant"},
        )
        db.add(txn)
        db.commit()

    return user


def get_user_balance(db: Session, public_key: str) -> int:
    """Get user's current balance in seconds."""
    user = db.query(User).filter(User.public_key == public_key).first()
    if not user:
        return 0
    return user.balance_seconds


def check_sufficient_balance(db: Session, public_key: str, estimated_duration: int = 300) -> bool:
    """Check if user has enough credits for estimated job duration."""
    balance = get_user_balance(db, public_key)
    return balance >= estimated_duration


def reserve_credits(db: Session, public_key: str, amount: int) -> bool:
    """Reserve credits for a job (deduct from balance)."""
    user = db.query(User).filter(User.public_key == public_key).first()
    if not user or user.balance_seconds < amount:
        return False

    user.balance_seconds -= amount
    user.last_active = datetime.utcnow()
    db.commit()
    return True


def refund_credits(db: Session, public_key: str, amount: int, job_id: str):
    """Refund unused credits (e.g., if job failed early)."""
    user = db.query(User).filter(User.public_key == public_key).first()
    if not user:
        return

    user.balance_seconds += amount
    db.commit()

    # Record refund transaction
    txn = Transaction(
        from_user=None,
        to_user=public_key,
        duration_seconds=0,
        credits_transferred=amount,
        job_id=job_id,
        node_id=None,
        timestamp=datetime.utcnow(),
        metadata={"type": "refund"},
    )
    db.add(txn)
    db.commit()


def record_job_completion(
    db: Session,
    job_id: str,
    requester_public_key: str,
    worker_node_id: str,
    duration_seconds: int,
    receipt_signature: str,
) -> dict:
    """
    Record completed job and transfer credits from requester to worker owner.
    Verifies HMAC signature to prevent fraud.

    Returns: {"status": "success"} or {"status": "error", "message": "..."}
    """
    # Verify HMAC signature
    expected_signature = generate_receipt_signature(job_id, worker_node_id, duration_seconds)
    if not hmac.compare_digest(receipt_signature, expected_signature):
        return {"status": "error", "message": "Invalid receipt signature"}

    # Get worker node to find owner
    node = db.query(Node).filter(Node.node_id == worker_node_id).first()
    if not node:
        return {"status": "error", "message": "Worker node not found"}

    worker_public_key = node.owner_public_key

    # Get multiplier for credits calculation
    multiplier = node.multiplier
    credits_to_transfer = int(duration_seconds * multiplier)

    # Get users
    requester = db.query(User).filter(User.public_key == requester_public_key).first()
    worker_owner = db.query(User).filter(User.public_key == worker_public_key).first()

    if not requester:
        return {"status": "error", "message": "Requester not found"}

    # Create worker owner if doesn't exist (they earn credits)
    if not worker_owner:
        worker_owner = create_user_if_not_exists(db, worker_public_key)

    # Transfer credits (requester already had credits reserved, now we confirm the charge)
    # The actual deduction happened in reserve_credits, so we just add to worker
    worker_owner.balance_seconds += credits_to_transfer

    # Update node stats
    node.total_jobs_completed += 1
    node.last_seen = datetime.utcnow()

    # Update trust score (simple increment for now)
    node.trust_score = min(1.0, node.trust_score + 0.01)

    # Record transaction
    txn = Transaction(
        from_user=requester_public_key,
        to_user=worker_public_key,
        duration_seconds=duration_seconds,
        credits_transferred=credits_to_transfer,
        job_id=job_id,
        node_id=worker_node_id,
        timestamp=datetime.utcnow(),
        metadata={"type": "job_completion", "multiplier": multiplier},
    )
    db.add(txn)
    db.commit()

    return {
        "status": "success",
        "credits_transferred": credits_to_transfer,
        "requester_balance": requester.balance_seconds,
        "worker_balance": worker_owner.balance_seconds,
    }


def generate_receipt_signature(job_id: str, node_id: str, duration_seconds: int) -> str:
    """Generate HMAC signature for job receipt."""
    message = f"{job_id}:{node_id}:{duration_seconds}".encode()
    signature = hmac.new(RECEIPT_SECRET.encode(), message, hashlib.sha256).hexdigest()
    return signature


def get_transaction_history(db: Session, public_key: str, limit: int = 50) -> list[dict]:
    """Get transaction history for a user."""
    transactions = (
        db.query(Transaction)
        .filter((Transaction.from_user == public_key) | (Transaction.to_user == public_key))
        .order_by(Transaction.timestamp.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": txn.id,
            "from_user": txn.from_user,
            "to_user": txn.to_user,
            "credits": txn.credits_transferred,
            "duration": txn.duration_seconds,
            "job_id": txn.job_id,
            "timestamp": txn.timestamp.isoformat(),
            "type": txn.metadata.get("type") if txn.metadata else "job",
        }
        for txn in transactions
    ]
