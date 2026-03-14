import pytest
from unittest.mock import MagicMock
from coordinator.application.accounting_services import AccountingService
from coordinator.domain.accounting.models import User


@pytest.fixture
def mock_user_repo():
    return MagicMock()


@pytest.fixture
def mock_txn_repo():
    return MagicMock()


@pytest.fixture
def accounting_service(mock_user_repo, mock_txn_repo):
    return AccountingService(mock_user_repo, mock_txn_repo)


def test_create_user_if_not_exists_new_user(accounting_service, mock_user_repo, mock_txn_repo):
    mock_user_repo.get_by_public_key.return_value = None

    public_key = "new_user"
    user = accounting_service.create_user_if_not_exists(public_key, 3600)

    assert user.public_key == public_key
    assert user.balance.seconds == 3600
    mock_user_repo.save.assert_called_once()
    mock_txn_repo.record_transaction.assert_called_once()

    txn = mock_txn_repo.record_transaction.call_args[0][0]
    assert txn.type == "starter_grant"
    assert txn.to_user == public_key
    assert txn.amount.seconds == 3600


def test_create_user_if_not_exists_existing_user(accounting_service, mock_user_repo, mock_txn_repo):
    existing_user = User.create_new("existing_user", 5000)
    mock_user_repo.get_by_public_key.return_value = existing_user

    user = accounting_service.create_user_if_not_exists("existing_user")

    assert user == existing_user
    mock_user_repo.save.assert_not_called()
    mock_txn_repo.record_transaction.assert_not_called()


def test_reserve_credits_success(accounting_service, mock_user_repo):
    user = User.create_new("user1", 1000)
    mock_user_repo.get_by_public_key.return_value = user

    result = accounting_service.reserve_credits("user1", 400)

    assert result is True
    assert user.balance.seconds == 600
    mock_user_repo.save.assert_called_once_with(user)


def test_reserve_credits_insufficient(accounting_service, mock_user_repo):
    user = User.create_new("user1", 100)
    mock_user_repo.get_by_public_key.return_value = user

    result = accounting_service.reserve_credits("user1", 400)

    assert result is False
    assert user.balance.seconds == 100
    mock_user_repo.save.assert_not_called()


def test_reserve_credits_user_not_found(accounting_service, mock_user_repo):
    mock_user_repo.get_by_public_key.return_value = None
    result = accounting_service.reserve_credits("nonexistent", 100)
    assert result is False


def test_process_job_completion_success(accounting_service, mock_user_repo, mock_txn_repo):
    requester = User.create_new("requester", 1000)
    worker_owner = User.create_new("worker_owner", 500)

    # Mocking get_by_public_key for both
    mock_user_repo.get_by_public_key.side_effect = [requester, worker_owner]

    result = accounting_service.process_job_completion(
        job_id="job1",
        requester_pk="requester",
        worker_node_id="node1",
        worker_owner_pk="worker_owner",
        duration_seconds=100,
        multiplier=2.0,
    )

    assert result["status"] == "success"
    assert result["credits_transferred"] == 200
    assert worker_owner.balance.seconds == 700
    mock_user_repo.save.assert_called_once_with(worker_owner)
    mock_txn_repo.record_transaction.assert_called_once()

    txn = mock_txn_repo.record_transaction.call_args[0][0]
    assert txn.job_id == "job1"
    assert txn.from_user == "requester"
    assert txn.to_user == "worker_owner"
    assert txn.amount.seconds == 200


def test_process_job_completion_requester_not_found(accounting_service, mock_user_repo):
    mock_user_repo.get_by_public_key.return_value = None

    result = accounting_service.process_job_completion(
        job_id="job1",
        requester_pk="missing",
        worker_node_id="node1",
        worker_owner_pk="worker",
        duration_seconds=100,
        multiplier=1.0,
    )

    assert result["status"] == "error"
    assert "Requester not found" in result["message"]


def test_process_job_completion_worker_owner_not_exists(
    accounting_service, mock_user_repo, mock_txn_repo
):
    requester = User.create_new("requester", 1000)

    # First call for requester, second for worker_owner (None),
    # third call (from inside create_user_if_not_exists) for worker_owner (None),
    # fourth call (from inside process_job_completion) for worker_owner (the new one)
    new_worker_owner = User.create_new("new_worker", 0)
    mock_user_repo.get_by_public_key.side_effect = [
        requester,
        None,
        None,
        new_worker_owner,
    ]

    result = accounting_service.process_job_completion(
        job_id="job1",
        requester_pk="requester",
        worker_node_id="node1",
        worker_owner_pk="new_worker",
        duration_seconds=100,
        multiplier=1.0,
    )

    assert result["status"] == "success"
    assert result["credits_transferred"] == 100
    assert new_worker_owner.balance.seconds == 100

    # save called twice: once in create_user_if_not_exists, once in process_job_completion
    assert mock_user_repo.save.call_count == 2
