from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from coordinator.application.inference_services import DiscoveryService
from coordinator.domain.inference.models import HardwareSpec, Node
from coordinator.domain.inference.reputation import (
    NodeReputation,
    ReputationComponents,
    ReputationScore,
)


@pytest.fixture
def mock_discovery_repo():
    return MagicMock()


@pytest.fixture
def mock_reputation_repo():
    return MagicMock()


@pytest.fixture
def discovery_service(mock_discovery_repo, mock_reputation_repo):
    return DiscoveryService(mock_discovery_repo, mock_reputation_repo)


def _make_node(node_id, status="IDLE", models=None):
    return Node(
        node_id=node_id,
        tailscale_ip=f"100.1.1.{node_id[-1]}",
        status=status,
        models=models or ["m1"],
        hardware=HardwareSpec("GPU", 1000),
        engines=[],
    )


def _make_reputation(node_id, score_value):
    return NodeReputation(
        node_id=node_id,
        score=ReputationScore(score_value),
        components=ReputationComponents(availability=1.0, reliability=1.0, performance=1.0),
        total_jobs=10,
        successful_jobs=10,
        failed_jobs=0,
        total_heartbeats_expected=100,
        total_heartbeats_received=100,
        updated_at=datetime.now(timezone.utc),
    )


def test_register_heartbeat(discovery_service, mock_discovery_repo, mock_reputation_repo):
    node = _make_node("node1")
    discovery_service.register_heartbeat(node, ttl_seconds=20)
    mock_discovery_repo.save_node.assert_called_once_with(node, 20)
    mock_reputation_repo.record_heartbeat.assert_called_once_with("node1")


def test_select_node_for_model_none_idle(discovery_service, mock_discovery_repo):
    node1 = _make_node("n1", status="BUSY")
    mock_discovery_repo.find_nodes_by_model.return_value = [node1]

    selected = discovery_service.select_node_for_model("m1")
    assert selected is None


def test_select_node_for_model_no_nodes(discovery_service, mock_discovery_repo):
    mock_discovery_repo.find_nodes_by_model.return_value = []
    selected = discovery_service.select_node_for_model("unknown")
    assert selected is None


def test_select_node_weighted_prefers_high_reputation(
    discovery_service, mock_discovery_repo, mock_reputation_repo
):
    """High-reputation nodes should be selected more frequently."""
    high_rep_node = _make_node("n1")
    low_rep_node = _make_node("n2")

    mock_discovery_repo.find_nodes_by_model.return_value = [high_rep_node, low_rep_node]

    def get_rep(node_id):
        if node_id == "n1":
            return _make_reputation("n1", 0.95)
        return _make_reputation("n2", 0.3)

    mock_reputation_repo.get_reputation.side_effect = get_rep

    # Run selection many times — high-rep node should dominate
    selections = {}
    for _ in range(200):
        selected = discovery_service.select_node_for_model("m1")
        selections[selected.node_id] = selections.get(selected.node_id, 0) + 1

    assert selections.get("n1", 0) > selections.get("n2", 0)


def test_select_node_excludes_suspended(
    discovery_service, mock_discovery_repo, mock_reputation_repo
):
    """Suspended nodes (score < 0.2) should never be selected."""
    good_node = _make_node("n1")
    suspended_node = _make_node("n2")

    mock_discovery_repo.find_nodes_by_model.return_value = [good_node, suspended_node]

    def get_rep(node_id):
        if node_id == "n1":
            return _make_reputation("n1", 0.8)
        return _make_reputation("n2", 0.1)  # SUSPENDED tier

    mock_reputation_repo.get_reputation.side_effect = get_rep

    for _ in range(50):
        selected = discovery_service.select_node_for_model("m1")
        assert selected.node_id == "n1"


def test_select_node_all_suspended_returns_none(
    discovery_service, mock_discovery_repo, mock_reputation_repo
):
    """If all nodes are suspended, return None."""
    node = _make_node("n1")
    mock_discovery_repo.find_nodes_by_model.return_value = [node]
    mock_reputation_repo.get_reputation.return_value = _make_reputation("n1", 0.1)

    selected = discovery_service.select_node_for_model("m1")
    assert selected is None


def test_get_aggregated_models(discovery_service, mock_discovery_repo):
    n1 = _make_node("n1", models=["m1", "m2"])
    n2 = _make_node("n2", models=["m2", "m3"])
    mock_discovery_repo.list_all_active_nodes.return_value = [n1, n2]

    models = discovery_service.get_aggregated_models()
    assert models == ["m1", "m2", "m3"]


def test_list_peers_sorted_by_reputation(
    discovery_service, mock_discovery_repo, mock_reputation_repo
):
    """Peers should be sorted by reputation score descending."""
    n1 = _make_node("n1")
    n2 = _make_node("n2")
    n3 = _make_node("n3")

    mock_discovery_repo.list_all_active_nodes.return_value = [n1, n2, n3]

    def get_rep(node_id):
        scores = {"n1": 0.3, "n2": 0.9, "n3": 0.6}
        return _make_reputation(node_id, scores[node_id])

    mock_reputation_repo.get_reputation.side_effect = get_rep

    peers = discovery_service.list_peers()
    assert [p.node_id for p in peers] == ["n2", "n3", "n1"]


def test_list_peers_with_model_filter(discovery_service, mock_discovery_repo, mock_reputation_repo):
    mock_discovery_repo.find_nodes_by_model.return_value = []
    discovery_service.list_peers(model="m1")
    mock_discovery_repo.find_nodes_by_model.assert_called_once_with("m1")


def test_record_job_outcome(discovery_service, mock_reputation_repo):
    discovery_service.record_job_outcome("node1", success=True)
    mock_reputation_repo.record_job_outcome.assert_called_once_with("node1", True)

    discovery_service.record_job_outcome("node2", success=False)
    mock_reputation_repo.record_job_outcome.assert_called_with("node2", False)


def test_recalculate_reputation(discovery_service, mock_reputation_repo):
    mock_reputation_repo.get_reputation.return_value = _make_reputation("n1", 0.5)

    result = discovery_service.recalculate_reputation("n1")
    assert result is not None
    assert result.node_id == "n1"
    mock_reputation_repo.save_reputation.assert_called_once()


def test_recalculate_reputation_unknown_node(discovery_service, mock_reputation_repo):
    mock_reputation_repo.get_reputation.return_value = None
    result = discovery_service.recalculate_reputation("unknown")
    assert result is None
