import pytest
import sys
from unittest.mock import patch, MagicMock

# Create mocks
mock_sqlalchemy = MagicMock()
mock_sqlalchemy.ext = MagicMock()
mock_sqlalchemy.ext.declarative = MagicMock()
mock_sqlalchemy.orm = MagicMock()

@pytest.fixture(scope="module")
def db_module():
    """Mock sys.modules strictly for this test module to avoid polluting the global cache."""
    with patch.dict('sys.modules', {
        'sqlalchemy': mock_sqlalchemy,
        'sqlalchemy.ext': mock_sqlalchemy.ext,
        'sqlalchemy.ext.declarative': mock_sqlalchemy.ext.declarative,
        'sqlalchemy.orm': mock_sqlalchemy.orm,
    }):
        with patch("os.getenv", return_value="sqlite:///:memory:"):
            import infrastructure.persistence.database as db
            yield db

    # Clean up the imported module so it doesn't pollute subsequent tests
    if 'infrastructure.persistence.database' in sys.modules:
        del sys.modules['infrastructure.persistence.database']

def test_init_db(db_module):
    with patch.object(db_module, "Base") as mock_base:
        with patch.object(db_module, "engine") as mock_engine:
            db_module.init_db()
            mock_base.metadata.create_all.assert_called_once_with(bind=mock_engine)

def test_get_db(db_module):
    with patch.object(db_module, "SessionLocal") as mock_session_local:
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        gen = db_module.get_db()
        db = next(gen)

        assert db == mock_db
        mock_db.close.assert_not_called()

        with pytest.raises(StopIteration):
            next(gen)

        mock_db.close.assert_called_once()

def test_create_db_engine(db_module):
    with patch.object(db_module, "create_engine") as mock_create_engine:
        test_url = "postgresql://user:pass@localhost/db"
        db_module.create_db_engine(test_url)
        mock_create_engine.assert_called_once_with(test_url)
