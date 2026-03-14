from datetime import datetime
from unittest.mock import MagicMock

import pytest

from coordinator.application.verification_services import VerificationService
from coordinator.domain.verification.models import Challenge


@pytest.fixture
def mock_challenge_repo():
    return MagicMock()


@pytest.fixture
def mock_benchmark_repo():
    return MagicMock()


@pytest.fixture
def verification_service(mock_challenge_repo, mock_benchmark_repo):
    return VerificationService(mock_challenge_repo, mock_benchmark_repo)


def test_issue_challenge(verification_service, mock_challenge_repo):
    node_id = "node_1"
    challenge = verification_service.issue_challenge(node_id)

    assert challenge.node_id == node_id
    assert challenge.token is not None
    assert challenge.seed is not None
    mock_challenge_repo.save_challenge.assert_called_once_with(challenge, ttl_seconds=60)


def test_verify_proof_success(verification_service, mock_challenge_repo, mock_benchmark_repo):
    token = "token_123"
    node_id = "node_1"
    now = datetime.utcnow()
    challenge = Challenge(token, "seed", 1024, now, node_id)

    mock_challenge_repo.get_challenge.return_value = challenge

    result = verification_service.verify_proof(
        token=token, node_id=node_id, duration=10.0, device_name="RTX 4090", proof_hash="hash_123"
    )

    assert result["status"] == "verified"
    assert result["assigned_multiplier"] == 3.5  # 35.0 / 10.0
    assert result["tier"] == "High Performance"

    mock_benchmark_repo.save_result.assert_called_once()
    mock_challenge_repo.delete_challenge.assert_called_once_with(token)


def test_verify_proof_challenge_not_found(verification_service, mock_challenge_repo):
    mock_challenge_repo.get_challenge.return_value = None
    result = verification_service.verify_proof("t", "n", 10.0, "d", "h")
    assert result["status"] == "error"
    assert "Challenge expired or invalid" in result["message"]


def test_verify_proof_node_mismatch(verification_service, mock_challenge_repo):
    challenge = Challenge("t", "s", 1024, datetime.utcnow(), "node_1")
    mock_challenge_repo.get_challenge.return_value = challenge

    result = verification_service.verify_proof("t", "different_node", 10.0, "d", "h")
    assert result["status"] == "error"
    assert "Challenge node ID mismatch" in result["message"]


def test_verify_proof_tier_standard(verification_service, mock_challenge_repo):
    challenge = Challenge("t", "s", 1024, datetime.utcnow(), "node_1")
    mock_challenge_repo.get_challenge.return_value = challenge

    # 35.0 / 17.5 = 2.0 (<= 3.0, so Standard)
    result = verification_service.verify_proof("t", "node_1", 17.5, "d", "h")
    assert result["tier"] == "Standard"
