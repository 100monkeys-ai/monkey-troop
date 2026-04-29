import importlib
import os
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

import infrastructure.dependencies as deps
from infrastructure.dependencies import (
    get_accounting_service,
    get_discovery_service,
    get_redis_client,
    get_security_service,
    get_verification_service,
)


def test_dependency_providers():
    db = MagicMock(spec=Session)
    redis = MagicMock()

    # Test individual providers
    accounting = get_accounting_service(db)
    assert accounting is not None

    discovery = get_discovery_service(redis, db)
    assert discovery is not None

    verification = get_verification_service(db, redis)
    assert verification is not None

    security = get_security_service()
    assert security is not None

    client = get_redis_client()
    assert client is not None


def test_get_redis_client_configuration():
    # Save original environment to restore later if needed
    original_host = os.environ.get("REDIS_HOST")

    try:
        # Mock environment variable
        with patch.dict("os.environ", {"REDIS_HOST": "custom-redis-host"}):
            # Reload the module to pick up the new environment variable
            importlib.reload(deps)

            # Test the function
            client = deps.get_redis_client()

            # Verify it was configured correctly
            assert client.connection_pool.connection_kwargs.get("host") == "custom-redis-host"
            assert client.connection_pool.connection_kwargs.get("port") == 6379
            assert client.connection_pool.connection_kwargs.get("db") == 0
            assert client.connection_pool.connection_kwargs.get("decode_responses") is True

        # Mock empty environment to test default fallback
        with patch.dict("os.environ", {}, clear=True):
            importlib.reload(deps)
            client = deps.get_redis_client()
            assert client.connection_pool.connection_kwargs.get("host") == "localhost"
    finally:
        # Restore the module to its original state so we don't break other tests
        if original_host is not None:
            os.environ["REDIS_HOST"] = original_host
        elif "REDIS_HOST" in os.environ:
            del os.environ["REDIS_HOST"]
        importlib.reload(deps)
