import os
import importlib
import pytest
from fastapi.testclient import TestClient


def test_cors_default_secure():
    # Force reload of main to pick up default env
    if "ALLOWED_ORIGINS" in os.environ:
        del os.environ["ALLOWED_ORIGINS"]

    import main

    importlib.reload(main)
    from main import app

    client = TestClient(app)

    # Test that default origin is allowed
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"

    # Test that random origin is NOT allowed
    response = client.options(
        "/health",
        headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in response.headers


def test_cors_wildcard_rejection():
    # Mock ALLOWED_ORIGINS="*"
    os.environ["ALLOWED_ORIGINS"] = "*"

    import main

    importlib.reload(main)
    from main import app

    client = TestClient(app)

    # Wildcard should have been rejected and fallen back to default
    response = client.options(
        "/health",
        headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in response.headers

    # Should still allow default
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_multiple_origins_with_wildcard():
    # Mock ALLOWED_ORIGINS="http://trusted.com,*"
    os.environ["ALLOWED_ORIGINS"] = "http://trusted.com,*"

    import main

    importlib.reload(main)
    from main import app

    client = TestClient(app)

    # trusted.com should be allowed
    response = client.options(
        "/health",
        headers={
            "Origin": "http://trusted.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://trusted.com"

    # wildcard should be ignored
    response = client.options(
        "/health",
        headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in response.headers
