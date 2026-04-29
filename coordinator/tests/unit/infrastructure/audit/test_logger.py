from unittest.mock import MagicMock, patch


import json

import pytest

from coordinator.infrastructure.audit.logger import AuditService

@pytest.fixture
def mock_db_session():
    return MagicMock()

@pytest.fixture
def audit_service(mock_db_session):
    return AuditService(db_session=mock_db_session)

def test_log_event_success(audit_service, mock_db_session):
    with patch("coordinator.infrastructure.audit.logger.audit_logger") as mock_logger, \
         patch("coordinator.infrastructure.persistence.database.AuditLog") as mock_audit_log_cls:

        # Setup mock db
        mock_audit_entry = MagicMock()
        mock_audit_log_cls.return_value = mock_audit_entry

        audit_service.log_event("test_event", "user1", "127.0.0.1", {"key": "value"})

        # Verify file logging
        mock_logger.info.assert_called_once()
        log_call_args = mock_logger.info.call_args[0][0]
        log_data = json.loads(log_call_args)
        assert log_data["event"] == "test_event"
        assert log_data["key"] == "value"

        # Verify DB logging
        mock_audit_log_cls.assert_called_once_with(
            event_type="test_event",
            user_id="user1",
            ip_address="127.0.0.1",
            details={"key": "value"}
        )
        mock_db_session.add.assert_called_once_with(mock_audit_entry)
        mock_db_session.commit.assert_called_once()

def test_log_event_db_exception(audit_service, mock_db_session):
    with patch("coordinator.infrastructure.audit.logger.audit_logger") as mock_logger, \
         patch("coordinator.infrastructure.audit.logger.logging.error") as mock_logging_error, \
         patch("coordinator.infrastructure.persistence.database.AuditLog"):

        # Setup mock db to raise exception
        mock_db_session.commit.side_effect = Exception("DB Connection Error")

        audit_service.log_event("test_event", "user1", "127.0.0.1", {"key": "value"})

        # Verify file logging still happened
        mock_logger.info.assert_called_once()

        # Verify DB exception was caught and logged
        mock_logging_error.assert_called_once()
        error_msg = mock_logging_error.call_args[0][0]
        assert "Failed to write audit log to database: DB Connection Error" in error_msg

def test_get_logs(audit_service, mock_db_session):
    with patch("coordinator.infrastructure.audit.logger.db_models") as mock_db_models:
        # Setup mock db query
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query

        # Setup mock filter
        mock_filter1 = MagicMock()
        mock_query.filter.return_value = mock_filter1

        mock_filter2 = MagicMock()
        mock_filter1.filter.return_value = mock_filter2

        # Setup mock order_by, offset, limit, all
        mock_order_by = MagicMock()
        mock_filter2.order_by.return_value = mock_order_by
        mock_query.order_by.return_value = mock_order_by
        mock_filter1.order_by.return_value = mock_order_by

        mock_offset = MagicMock()
        mock_order_by.offset.return_value = mock_offset

        mock_limit = MagicMock()
        mock_offset.limit.return_value = mock_limit

        mock_log1 = MagicMock()
        mock_log1.id = 1
        mock_log1.timestamp.isoformat.return_value = "2023-01-01T12:00:00"
        mock_log1.event_type = "test_event"
        mock_log1.user_id = "user1"
        mock_log1.ip_address = "127.0.0.1"
        mock_log1.details = {"key": "value"}

        mock_limit.all.return_value = [mock_log1]

        # Fix the mock_db_models issue
        mock_db_models.AuditLog = MagicMock()
        mock_db_models.AuditLog.timestamp = MagicMock()
        mock_db_models.AuditLog.timestamp.desc.return_value = "desc_timestamp"

        # Test without filters
        logs = audit_service.get_logs()
        assert len(logs) == 1
        assert logs[0]["id"] == 1
        assert logs[0]["event_type"] == "test_event"
        mock_db_session.query.assert_called_once_with(mock_db_models.AuditLog)

        # Reset mock for next test
        mock_db_session.query.reset_mock()
        mock_query.filter.reset_mock()

        # Test with filters
        logs = audit_service.get_logs(event_type="test_event", user_id="user1")
        assert len(logs) == 1
        mock_db_session.query.assert_called_once_with(mock_db_models.AuditLog)
        assert mock_query.filter.call_count == 1
        assert mock_filter1.filter.call_count == 1
