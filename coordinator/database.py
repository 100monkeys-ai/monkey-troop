"""Database models and connection management."""

import os
from datetime import datetime

from sqlalchemy import (BigInteger, Column, DateTime, Float, ForeignKey,
                        Integer, String, create_engine)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://troop_admin:changeme@localhost:5432/troop_ledger"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class AuditLog(Base):
    """Audit log entries stored in PostgreSQL."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    event_type = Column(String(50), index=True, nullable=False)
    user_id = Column(String(255), index=True, nullable=True)
    ip_address = Column(String(45), nullable=True)
    details = Column(JSONB, nullable=True)


class User(Base):
    """User account with credit balance."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False)
    public_key = Column(String, unique=True, nullable=False)  # Wallet address
    balance_seconds = Column(BigInteger, default=3600)  # Start with 1 free hour
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    nodes = relationship("Node", back_populates="owner")
    transactions_sent = relationship(
        "Transaction", foreign_keys="Transaction.requester_id", back_populates="requester"
    )


class Node(Base):
    """GPU node in the network."""

    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    node_id = Column(String(50), unique=True, nullable=False)
    node_name = Column(String(50))
    hardware_model = Column(String(50))
    multiplier = Column(Float, default=1.0)  # Credit multiplier based on hardware
    benchmark_score = Column(Float)  # Seconds to complete standard task
    last_benchmark = Column(DateTime)
    trust_score = Column(Integer, default=100)  # Reputation
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="nodes")
    transactions = relationship(
        "Transaction", foreign_keys="Transaction.worker_node_id", back_populates="worker_node"
    )


class Transaction(Base):
    """Credit transaction ledger."""

    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, nullable=False, unique=True)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    worker_node_id = Column(Integer, ForeignKey("nodes.id"), nullable=False)
    duration_seconds = Column(Integer, nullable=False)
    credits_transferred = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    requester = relationship(
        "User", foreign_keys=[requester_id], back_populates="transactions_sent"
    )
    worker_node = relationship("Node", foreign_keys=[worker_node_id], back_populates="transactions")


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
