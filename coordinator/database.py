"""Database models and connection management."""

import os
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
)
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
    details = Column(JSON, nullable=True)


class User(Base):
    """User account with credit balance."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    public_key = Column(String, unique=True, nullable=False)  # Wallet address
    balance_seconds = Column(BigInteger, default=3600)  # Start with 1 free hour
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)


class Node(Base):
    """GPU node in the network."""

    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(String(50), unique=True, nullable=False)
    owner_public_key = Column(String, nullable=False, index=True)

    multiplier = Column(Float, default=1.0)  # Credit multiplier based on hardware
    benchmark_score = Column(Float)  # Seconds to complete standard task
    trust_score = Column(Integer, default=100)  # Reputation
    total_jobs_completed = Column(Integer, default=0)

    # Extra fields used in logic but maybe not in migration 001?
    # We should include them if code uses them.
    hardware_model = Column(String(50))
    last_benchmark = Column(DateTime)
    last_seen = Column(DateTime, default=datetime.utcnow)

    created_at = Column(DateTime, default=datetime.utcnow)


class Transaction(Base):
    """Credit transaction ledger."""

    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, nullable=True)  # Can be null for system grants

    from_user = Column(String, index=True, nullable=True)  # Public Key
    to_user = Column(String, index=True, nullable=True)  # Public Key

    node_id = Column(String, nullable=True)

    duration_seconds = Column(Integer, nullable=False)
    credits_transferred = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    meta_data = Column("metadata", JSON, nullable=True)  # Map to "metadata" column in DB


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
