import json
from unittest.mock import MagicMock, patch

import pytest

from coordinator.infrastructure.audit.logger import AuditService


@pytest.fixture
def mock_db_session():
    return MagicMock()


@pytest.fixture
def audit_service(mock_db_session):
    return AuditService(db_session=mock_db_session)


def test_log_event_success(audit_service, mock_db_session):
    with (
        patch("coordinator.infrastructure.audit.logger.audit_logger") as mock_logger,
        patch("coordinator.infrastructure.persistence.database.AuditLog") as mock_audit_log_cls,
    ):
        mock_audit_entry = MagicMock()
        mock_audit_log_cls.return_value = mock_audit_entry

        audit_service.log_event("test_event", "user1", "127.0.0.1", {"key": "value"})

        mock_logger.info.assert_called_once()
        log_data = json.loads(mock_logger.info.call_args[0][0])
        assert log_data["event"] == "test_event"
        assert log_data["key"] == "value"

        mock_audit_log_cls.assert_called_once_with(
            event_type="test_event",
            user_id="user1",
            ip_address="127.0.0.1",
            details={"key": "value"},
        )
        mock_db_session.add.assert_called_once_with(mock_audit_entry)
        mock_db_session.commit.assert_called_once()


def test_log_event_db_exception(audit_service, mock_db_session):
    with (
        patch("coordinator.infrastructure.audit.logger.audit_logger") as mock_logger,
        patch("coordinator.infrastructure.audit.logger.logging.error") as mock_logging_error,
        patch("coordinator.infrastructure.persistence.database.AuditLog"),
    ):
        mock_db_session.commit.side_effect = Exception("DB Connection Error")

        audit_service.log_event("test_event", "user1", "127.0.0.1", {"key": "value"})

        mock_logger.info.assert_called_once()
        mock_logging_error.assert_called_once()
        assert (
            "Failed to write audit log to database: DB Connection Error"
            in mock_logging_error.call_args[0][0]
        )


def test_get_logs_no_filters(audit_service, mock_db_session):
    with patch("coordinator.infrastructure.audit.logger.db_models") as mock_db_models:
        mock_log = MagicMock()
        mock_log.id = 1
        mock_log.timestamp.isoformat.return_value = "2023-01-01T12:00:00"
        mock_log.event_type = "test_event"
        mock_log.user_id = "user1"
        mock_log.ip_address = "127.0.0.1"
        mock_log.details = {"key": "value"}

        mock_chain = MagicMock()
        mock_chain.all.return_value = [mock_log]
        mock_db_session.query.return_value.order_by.return_value.offset.return_value.limit.return_value = (
            mock_chain
        )

        logs = audit_service.get_logs()

        assert len(logs) == 1
        assert logs[0]["id"] == 1
        assert logs[0]["event_type"] == "test_event"
        mock_db_session.query.assert_called_once_with(mock_db_models.AuditLog)


def test_get_logs_with_filters(audit_service, mock_db_session):
    with patch("coordinator.infrastructure.audit.logger.db_models") as mock_db_models:
        mock_log = MagicMock()
        mock_log.id = 2
        mock_log.timestamp.isoformat.return_value = "2023-01-02T08:00:00"
        mock_log.event_type = "login"
        mock_log.user_id = "user2"
        mock_log.ip_address = "10.0.0.1"
        mock_log.details = {}

        mock_chain = MagicMock()
        mock_chain.all.return_value = [mock_log]
        query_chain = mock_db_session.query.return_value
        limit_mock = (
            query_chain.filter.return_value
            .filter.return_value
            .order_by.return_value
            .offset.return_value
            .limit
        )
        limit_mock.return_value = mock_chain

        logs = audit_service.get_logs(event_type="login", user_id="user2")

        assert len(logs) == 1
        assert logs[0]["user_id"] == "user2"
        assert mock_db_session.query.return_value.filter.call_count == 1
        assert mock_db_session.query.return_value.filter.return_value.filter.call_count == 1
        _ = mock_db_models  # suppress unused-variable warning
