"""Audit logging for security and compliance."""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from database import AuditLog, SessionLocal

# Configure audit logger to write to separate file
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)

# File handler for audit logs
audit_handler = logging.FileHandler("logs/audit.log")
audit_handler.setFormatter(
    logging.Formatter(
        '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": %(message)s}'
    )
)
audit_logger.addHandler(audit_handler)


def _write_to_db(event_type: str, user_id: Optional[str], ip_address: str, details: dict):
    """Write audit log entry to PostgreSQL database."""
    try:
        db = SessionLocal()
        audit_entry = AuditLog(
            event_type=event_type, user_id=user_id, ip_address=ip_address, details=details
        )
        db.add(audit_entry)
        db.commit()
    except Exception as e:
        logging.error(f"Failed to write audit log to database: {e}")
    finally:
        db.close()


def log_authorization(
    requester_id: str, model: str, node_id: str, ip_address: str, success: bool, reason: str = ""
):
    """Log an authorization attempt."""
    details = {
        "event": "authorization",
        "requester_id": requester_id,
        "model": model,
        "node_id": node_id,
        "success": success,
        "reason": reason,
    }

    # Write to file
    audit_logger.info(json.dumps(details))

    # Write to database
    _write_to_db("authorization", requester_id, ip_address, details)


def log_transaction(
    job_id: str, requester_id: str, worker_id: str, duration: float, credits: float, ip_address: str
):
    """Log a completed transaction."""
    details = {
        "event": "transaction",
        "job_id": job_id,
        "requester_id": requester_id,
        "worker_id": worker_id,
        "duration": duration,
        "credits": credits,
    }

    # Write to file
    audit_logger.info(json.dumps(details))

    # Write to database
    _write_to_db("transaction", requester_id, ip_address, details)


def log_rate_limit(ip_address: str, endpoint: str, limit: int, window: int):
    """Log a rate limit violation."""
    details = {"event": "rate_limit", "endpoint": endpoint, "limit": limit, "window": window}

    # Write to file
    audit_logger.warning(json.dumps(details))

    # Write to database
    _write_to_db("rate_limit", None, ip_address, details)


def log_security_event(event_type: str, ip_address: Optional[str], details: dict):
    """Log a security event."""
    log_data = {"event": "security", "type": event_type, **details}

    # Write to file
    audit_logger.warning(json.dumps(log_data))

    # Write to database
    _write_to_db("security", details.get("user_id"), ip_address or "unknown", log_data)


def get_audit_logs(
    limit: int = 100,
    offset: int = 0,
    event_type: Optional[str] = None,
    user_id: Optional[str] = None,
) -> list[dict]:
    """Retrieve audit logs from database with filtering."""
    db = SessionLocal()

    query = db.query(AuditLog)

    if event_type:
        query = query.filter(AuditLog.event_type == event_type)

    if user_id:
        query = query.filter(AuditLog.user_id == user_id)

    logs = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()

    result = [
        {
            "id": log.id,
            "timestamp": log.timestamp.isoformat(),
            "event_type": log.event_type,
            "user_id": log.user_id,
            "ip_address": log.ip_address,
            "details": log.details,
        }
        for log in logs
    ]

    db.close()
    return result
