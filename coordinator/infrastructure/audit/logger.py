"""Infrastructure layer implementation for Audit Logging."""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from ..persistence import database as db_models
from sqlalchemy.orm import Session

# Configure audit logger
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)

os.makedirs("logs", exist_ok=True)

# File handler
if not audit_logger.handlers:
    audit_handler = logging.FileHandler("logs/audit.log")
    audit_handler.setFormatter(
        logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": %(message)s}'
        )
    )
    audit_logger.addHandler(audit_handler)


class AuditService:
    """Infrastructure service for auditing."""

    def __init__(self, db_session: Session):
        self.db = db_session

    def _write_to_db(
        self, event_type: str, user_id: Optional[str], ip_address: str, details: Dict[str, Any]
    ):
        try:
            audit_entry = db_models.AuditLog(
                event_type=event_type, user_id=user_id, ip_address=ip_address, details=details
            )
            self.db.add(audit_entry)
            self.db.commit()
        except Exception as e:
            logging.error(f"Failed to write audit log to database: {e}")

    def log_event(
        self, event_type: str, user_id: Optional[str], ip_address: str, details: Dict[str, Any]
    ):
        # Write to file
        audit_logger.info(json.dumps({**details, "event": event_type}))
        # Write to DB
        self._write_to_db(event_type, user_id, ip_address, details)

    def get_logs(
        self,
        limit: int = 100,
        offset: int = 0,
        event_type: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query = self.db.query(db_models.AuditLog)
        if event_type:
            query = query.filter(db_models.AuditLog.event_type == event_type)
        if user_id:
            query = query.filter(db_models.AuditLog.user_id == user_id)

        logs = query.order_by(db_models.AuditLog.timestamp.desc()).offset(offset).limit(limit).all()
        return [
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
