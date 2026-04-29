import os
import sys
from unittest.mock import MagicMock

# Mock dependencies that might be missing in the environment
# to allow importing 'main' for unit testing the CORS logic.
if "fastapi" not in sys.modules:
    sys.modules["fastapi"] = MagicMock()
if "fastapi.middleware.cors" not in sys.modules:
    sys.modules["fastapi.middleware.cors"] = MagicMock()
if "infrastructure.persistence.database" not in sys.modules:
    sys.modules["infrastructure.persistence.database"] = MagicMock()
if "infrastructure.security.key_repository" not in sys.modules:
    sys.modules["infrastructure.security.key_repository"] = MagicMock()
if "interface.api.accounting" not in sys.modules:
    sys.modules["interface.api.accounting"] = MagicMock()
if "interface.api.inference" not in sys.modules:
    sys.modules["interface.api.inference"] = MagicMock()
if "interface.api.security" not in sys.modules:
    sys.modules["interface.api.security"] = MagicMock()
if "interface.api.verification" not in sys.modules:
    sys.modules["interface.api.verification"] = MagicMock()

# Now we can import from main
try:
    from main import get_allowed_origins
except ImportError:
    # Handle cases where PYTHONPATH might not include the coordinator directory
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from main import get_allowed_origins

def test_get_allowed_origins_default():
    """Test default allowed origins when env var is not set."""
    old_val = os.environ.get("ALLOWED_ORIGINS")
    if "ALLOWED_ORIGINS" in os.environ:
        del os.environ["ALLOWED_ORIGINS"]
    try:
        assert get_allowed_origins() == ["http://localhost:3000"]
    finally:
        if old_val is not None:
            os.environ["ALLOWED_ORIGINS"] = old_val

def test_get_allowed_origins_custom():
    """Test custom allowed origins from env var."""
    old_val = os.environ.get("ALLOWED_ORIGINS")
    os.environ["ALLOWED_ORIGINS"] = "https://example.com, https://app.example.com"
    try:
        assert get_allowed_origins() == ["https://example.com", "https://app.example.com"]
    finally:
        if old_val is not None:
            os.environ["ALLOWED_ORIGINS"] = old_val
        else:
            del os.environ["ALLOWED_ORIGINS"]

def test_get_allowed_origins_filters_wildcard():
    """Test that wildcard is filtered out."""
    old_val = os.environ.get("ALLOWED_ORIGINS")
    os.environ["ALLOWED_ORIGINS"] = "https://example.com, *, http://localhost:3000"
    try:
        assert get_allowed_origins() == ["https://example.com", "http://localhost:3000"]
    finally:
        if old_val is not None:
            os.environ["ALLOWED_ORIGINS"] = old_val
        else:
            del os.environ["ALLOWED_ORIGINS"]

def test_get_allowed_origins_wildcard_only():
    """Test that only wildcard defaults to local."""
    old_val = os.environ.get("ALLOWED_ORIGINS")
    os.environ["ALLOWED_ORIGINS"] = "*"
    try:
        assert get_allowed_origins() == ["http://localhost:3000"]
    finally:
        if old_val is not None:
            os.environ["ALLOWED_ORIGINS"] = old_val
        else:
            del os.environ["ALLOWED_ORIGINS"]
