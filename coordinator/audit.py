"""Audit logging for security and compliance."""

import logging
from datetime import datetime, timedelta
from typing import Optional
import json

# Configure audit logger to write to separate file
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)

# File handler for audit logs
audit_handler = logging.FileHandler("logs/audit.log")
audit_handler.setFormatter(logging.Formatter(
    '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": %(message)s}'
))
audit_logger.addHandler(audit_handler)


def log_authorization(
    requester_id: str,
    model: str,
    node_id: str,
    ip_address: str,
    success: bool,
    reason: Optional[str] = None
):
    """Log authorization attempt."""
    audit_logger.info(json.dumps({
        "event": "authorization",
        "requester_id": requester_id,
        "model": model,
        "node_id": node_id,
        "ip_address": ip_address,
        "success": success,
        "reason": reason
    }))


def log_transaction(
    job_id: str,
    requester_id: str,
    worker_id: str,
    duration: int,
    credits: int,
    ip_address: str
):
    """Log credit transaction."""
    audit_logger.info(json.dumps({
        "event": "transaction",
        "job_id": job_id,
        "requester_id": requester_id,
        "worker_id": worker_id,
        "duration": duration,
        "credits": credits,
        "ip_address": ip_address
    }))


def log_rate_limit(
    ip_address: str,
    endpoint: str,
    limit: int,
    window: int
):
    """Log rate limit violation."""
    audit_logger.warning(json.dumps({
        "event": "rate_limit",
        "ip_address": ip_address,
        "endpoint": endpoint,
        "limit": limit,
        "window": window
    }))


def log_security_event(
    event_type: str,
    details: dict,
    ip_address: Optional[str] = None
):
    """Log security-related event."""
    audit_logger.warning(json.dumps({
        "event": "security",
        "type": event_type,
        "ip_address": ip_address,
        **details
    }))
