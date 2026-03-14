"""Pytest fixtures for Monkey Troop Coordinator."""

import fakeredis
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from infrastructure.persistence import database

# Use in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def redis_client():
    """Return a fake redis client."""
    return fakeredis.FakeStrictRedis(decode_responses=True)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():

    # Globally override the database engine and sessionmaker
    test_engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
    test_session_local = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    # Monkeypatch the database module
    database.engine = test_engine
    database.SessionLocal = test_session_local
    database.Base.metadata.create_all(bind=test_engine)

    yield test_engine

    database.Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session(setup_test_database):
    """Return a clean database session for each test."""
    connection = setup_test_database.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
