from infrastructure.dependencies import (
    get_accounting_service,
    get_discovery_service,
    get_verification_service,
    get_security_service,
    get_redis_client,
)
from sqlalchemy.orm import Session
from unittest.mock import MagicMock


def test_dependency_providers():
    db = MagicMock(spec=Session)
    redis = MagicMock()

    # Test individual providers
    accounting = get_accounting_service(db)
    assert accounting is not None

    discovery = get_discovery_service(redis)
    assert discovery is not None

    verification = get_verification_service(db, redis)
    assert verification is not None

    security = get_security_service()
    assert security is not None

    client = get_redis_client()
    assert client is not None
