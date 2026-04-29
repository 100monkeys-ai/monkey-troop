from unittest.mock import MagicMock

import pytest

from coordinator.application.orchestration_services import (
    AuthorizationResult,
    InsufficientCreditsError,
    NoNodesAvailableError,
    OrchestrationService,
)
from coordinator.domain.accounting.models import JobCompletionParams


@pytest.fixture
def mock_accounting_service():
    return MagicMock()


@pytest.fixture
def mock_discovery_service():
    return MagicMock()


@pytest.fixture
def mock_security_service():
    return MagicMock()


@pytest.fixture
def orchestration_service(mock_accounting_service, mock_discovery_service, mock_security_service):
    return OrchestrationService(
        accounting_service=mock_accounting_service,
        discovery_service=mock_discovery_service,
        security_service=mock_security_service,
    )


def test_authorize_inference_success(
    orchestration_service, mock_accounting_service, mock_discovery_service, mock_security_service
):
    # Setup mocks
    mock_user = MagicMock()
    mock_user.balance.seconds = 1000
    mock_accounting_service.create_user_if_not_exists.return_value = mock_user

    mock_node = MagicMock()
    mock_node.node_id = "node1"
    mock_node.tailscale_ip = "1.2.3.4"
    mock_node.encryption_public_key = "key1"
    mock_discovery_service.select_node_for_model.return_value = mock_node

    mock_ticket = MagicMock()
    mock_ticket.token = "tok123"
    mock_security_service.issue_authorization_ticket.return_value = mock_ticket

    # Execute
    result = orchestration_service.authorize_inference("user1", "gpt-4")

    # Assert
    assert isinstance(result, AuthorizationResult)
    assert result.target_ip == "1.2.3.4"
    assert result.token == "tok123"
    assert result.estimated_cost == 300
    assert result.encryption_public_key == "key1"

    mock_accounting_service.create_user_if_not_exists.assert_called_once_with("user1")
    mock_discovery_service.select_node_for_model.assert_called_once_with("gpt-4")
    mock_security_service.issue_authorization_ticket.assert_called_once_with("user1", "node1")


def test_authorize_inference_insufficient_credits(orchestration_service, mock_accounting_service):
    # Setup mock user with less than 300 credits
    mock_user = MagicMock()
    mock_user.balance.seconds = 200
    mock_accounting_service.create_user_if_not_exists.return_value = mock_user

    # Execute and Assert
    with pytest.raises(InsufficientCreditsError):
        orchestration_service.authorize_inference("user1", "gpt-4")


def test_authorize_inference_no_nodes(
    orchestration_service, mock_accounting_service, mock_discovery_service
):
    # Setup mock user with enough credits
    mock_user = MagicMock()
    mock_user.balance.seconds = 1000
    mock_accounting_service.create_user_if_not_exists.return_value = mock_user

    # Setup discovery to return None
    mock_discovery_service.select_node_for_model.return_value = None

    # Execute and Assert
    with pytest.raises(NoNodesAvailableError):
        orchestration_service.authorize_inference("user1", "gpt-4")


def test_complete_job_success(
    orchestration_service, mock_accounting_service, mock_discovery_service
):
    # Setup mocks
    mock_accounting_service.process_job_completion.return_value = {"status": "success"}

    # Execute
    params = JobCompletionParams(
        job_id="job123",
        requester_pk="user1",
        worker_node_id="node1",
        worker_owner_pk="owner1",
        duration_seconds=100,
        multiplier=1.0,
    )
    result = orchestration_service.complete_job(params, success=True)

    # Assert
    assert result == {"status": "success"}
    mock_accounting_service.process_job_completion.assert_called_once_with(params)
    mock_discovery_service.record_job_outcome.assert_called_once_with("node1", True)
    mock_discovery_service.recalculate_reputation.assert_called_once_with("node1")


def test_complete_job_failure(
    orchestration_service, mock_accounting_service, mock_discovery_service
):
    # Execute with success=False
    params = JobCompletionParams(
        job_id="job123",
        requester_pk="user1",
        worker_node_id="node1",
        worker_owner_pk="owner1",
        duration_seconds=100,
        multiplier=1.0,
    )
    result = orchestration_service.complete_job(params, success=False)

    # Assert
    assert result == {"status": "failed"}
    mock_accounting_service.process_job_completion.assert_not_called()
    mock_discovery_service.record_job_outcome.assert_called_once_with("node1", False)
    mock_discovery_service.recalculate_reputation.assert_called_once_with("node1")
