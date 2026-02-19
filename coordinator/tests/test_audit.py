"""Test audit logging functionality."""

import json
import os

import pytest
from audit import (log_authorization, log_rate_limit, log_security_event,
                   log_transaction)


def test_audit_log_created():
    """Test that audit log file is created."""
    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)

    # Log an event
    log_authorization("user1", "llama2", "node1", "127.0.0.1", True, None)

    # Check file exists
    assert os.path.exists("logs/audit.log")


def test_audit_entries_valid_json():
    """Test that audit log entries are valid JSON."""
    os.makedirs("logs", exist_ok=True)

    log_authorization("user_json", "model_json", "node_json", "1.2.3.4", False, "test_reason")

    with open("logs/audit.log", "r") as f:
        lines = f.readlines()
        # Parse last line
        if lines:
            last_entry = json.loads(lines[-1])
            assert "timestamp" in last_entry
            assert "message" in last_entry
            # The message field contains the nested JSON
            message = json.loads(last_entry["message"])
            assert message["event"] == "authorization"
            assert message["requester_id"] == "user_json"


def test_security_event_logging():
    """Test security event logging."""
    os.makedirs("logs", exist_ok=True)

    log_security_event("invalid_token", {"token": "abc123", "reason": "expired"}, "10.0.0.1")

    # Verify logged
    assert os.path.exists("logs/audit.log")
