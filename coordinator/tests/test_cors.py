"""Tests for CORS configuration in main.py."""

import pytest


def parse_allowed_origins(allowed_origins_raw):
    """
    Parse and validate ALLOWED_ORIGINS environment variable.
    Returns tuple of (allowed_origins list, allow_credentials bool).

    This replicates the logic in main.py for testing purposes.
    """
    if allowed_origins_raw == "*":
        return ["*"], False
    elif allowed_origins_raw:
        allowed_origins = [
            origin.strip() for origin in allowed_origins_raw.split(",") if origin.strip()
        ]
        if not allowed_origins:
            # If the result is empty after parsing (e.g., only commas), use default
            return ["http://localhost:3000"], True
        elif "*" in allowed_origins and len(allowed_origins) > 1:
            raise RuntimeError(
                "Invalid ALLOWED_ORIGINS configuration: '*' cannot be combined with other "
                "origins when credentials are allowed. Either set ALLOWED_ORIGINS='*' "
                "to disable credentials, or remove '*' from the list."
            )
        else:
            return allowed_origins, True
    else:
        # Default to local development if not specified
        return ["http://localhost:3000"], True


def test_cors_wildcard_disables_credentials():
    """Test that ALLOWED_ORIGINS='*' sets allow_credentials=False."""
    origins, credentials = parse_allowed_origins("*")
    assert origins == ["*"]
    assert credentials is False


def test_cors_specific_origins_enables_credentials():
    """Test that specific origins in ALLOWED_ORIGINS sets allow_credentials=True."""
    origins, credentials = parse_allowed_origins(
        "https://app.example.com,https://admin.example.com"
    )
    assert origins == ["https://app.example.com", "https://admin.example.com"]
    assert credentials is True


def test_cors_default_localhost():
    """Test that empty ALLOWED_ORIGINS defaults to http://localhost:3000."""
    origins, credentials = parse_allowed_origins("")
    assert origins == ["http://localhost:3000"]
    assert credentials is True


def test_cors_single_origin():
    """Test that a single origin is properly parsed."""
    origins, credentials = parse_allowed_origins("https://example.com")
    assert origins == ["https://example.com"]
    assert credentials is True


def test_cors_comma_separated_origins_parsed():
    """Test that comma-separated origins are properly parsed."""
    origins, credentials = parse_allowed_origins(
        "http://localhost:3000,https://example.com,https://app.example.com"
    )
    assert origins == ["http://localhost:3000", "https://example.com", "https://app.example.com"]
    assert credentials is True


def test_cors_wildcard_with_other_origins_raises_error():
    """Test that combining '*' with other origins raises a RuntimeError."""
    with pytest.raises(RuntimeError, match="Invalid ALLOWED_ORIGINS configuration"):
        parse_allowed_origins("*,http://example.com")


def test_cors_wildcard_in_middle_raises_error():
    """Test that '*' in the middle of origins list raises a RuntimeError."""
    with pytest.raises(RuntimeError, match="Invalid ALLOWED_ORIGINS configuration"):
        parse_allowed_origins("http://example.com,*,http://another.com")


def test_cors_wildcard_at_end_raises_error():
    """Test that '*' at the end of origins list raises a RuntimeError."""
    with pytest.raises(RuntimeError, match="Invalid ALLOWED_ORIGINS configuration"):
        parse_allowed_origins("http://example.com,*")


def test_cors_whitespace_handling():
    """Test that whitespace in comma-separated list is properly handled."""
    origins, credentials = parse_allowed_origins(
        " http://localhost:3000 , https://example.com , https://app.example.com "
    )
    assert origins == ["http://localhost:3000", "https://example.com", "https://app.example.com"]
    assert credentials is True


def test_cors_empty_entries_ignored():
    """Test that empty entries between commas are ignored."""
    origins, credentials = parse_allowed_origins("http://localhost:3000,,https://example.com")
    assert origins == ["http://localhost:3000", "https://example.com"]
    assert credentials is True


def test_cors_only_commas_defaults_to_localhost():
    """Test that a string with only commas defaults to localhost after parsing."""
    origins, credentials = parse_allowed_origins(",,,")
    assert origins == ["http://localhost:3000"]
    assert credentials is True
