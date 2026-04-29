from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from coordinator.application.inference_services import DiscoveryService
from coordinator.domain.inference.models import HardwareSpec, ModelIdentity, Node
from coordinator.domain.inference.reputation import (
    NodeReputation,
    ReputationComponents,
    ReputationScore,
)


def _mi(name: str, content_hash: str = "sha256:default", size_bytes: int = 1000) -> ModelIdentity:
    return ModelIdentity(name=name, content_hash=content_hash, size_bytes=size_bytes)


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
        models=models or [_mi("m1")],
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


def test_select_node_for_model_by_name(
    discovery_service, mock_discovery_repo, mock_reputation_repo
):
    node1 = Node("n1", "ip1", "IDLE", [_mi("m1")], HardwareSpec("g1", 1), [])
    node2 = Node("n2", "ip2", "BUSY", [_mi("m1")], HardwareSpec("g1", 1), [])

    mock_discovery_repo.find_nodes_by_model.return_value = [node1, node2]
    mock_reputation_repo.get_reputations_batch.return_value = []

    selected = discovery_service.select_node_for_model("m1")
    assert selected == node1
    mock_discovery_repo.find_nodes_by_model.assert_called_once_with("m1")


def test_select_node_for_model_by_hash(
    discovery_service, mock_discovery_repo, mock_reputation_repo
):
    node1 = Node(
        "n1", "ip1", "IDLE", [_mi("m1", content_hash="sha256:abc")], HardwareSpec("g1", 1), []
    )
    mock_discovery_repo.find_nodes_by_model.return_value = [node1]
    mock_reputation_repo.get_reputations_batch.return_value = []

    selected = discovery_service.select_node_for_model("sha256:abc")
    assert selected == node1
    mock_discovery_repo.find_nodes_by_model.assert_called_once_with("sha256:abc")


def test_select_node_for_model_none_idle(discovery_service, mock_discovery_repo):
    node1 = Node("n1", "ip1", "BUSY", [_mi("m1")], HardwareSpec("g1", 1), [])
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

    def get_reps_batch(node_ids):
        res = []
        if "n1" in node_ids:
            res.append(_make_reputation("n1", 0.95))
        if "n2" in node_ids:
            res.append(_make_reputation("n2", 0.3))
        return res

    mock_reputation_repo.get_reputations_batch.side_effect = get_reps_batch

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

    def get_reps_batch(node_ids):
        res = []
        if "n1" in node_ids:
            res.append(_make_reputation("n1", 0.8))
        if "n2" in node_ids:
            res.append(_make_reputation("n2", 0.1))  # SUSPENDED tier
        return res

    mock_reputation_repo.get_reputations_batch.side_effect = get_reps_batch

    for _ in range(50):
        selected = discovery_service.select_node_for_model("m1")
        assert selected.node_id == "n1"


def test_select_node_all_suspended_returns_none(
    discovery_service, mock_discovery_repo, mock_reputation_repo
):
    """If all nodes are suspended, return None."""
    node = _make_node("n1")
    mock_discovery_repo.find_nodes_by_model.return_value = [node]
    mock_reputation_repo.get_reputations_batch.return_value = [_make_reputation("n1", 0.1)]

    selected = discovery_service.select_node_for_model("m1")
    assert selected is None


def test_get_aggregated_models(discovery_service, mock_discovery_repo):
    m1 = _mi("alpha", content_hash="sha256:aaa", size_bytes=100)
    m2 = _mi("beta", content_hash="sha256:bbb", size_bytes=200)
    m3 = _mi("gamma", content_hash="sha256:ccc", size_bytes=300)
    n1 = Node("n1", "ip1", "IDLE", [m1, m2], HardwareSpec("g1", 1), [])
    n2 = Node("n2", "ip2", "IDLE", [m2, m3], HardwareSpec("g1", 1), [])
    mock_discovery_repo.list_all_active_nodes.return_value = [n1, n2]

    models = discovery_service.get_aggregated_models()
    assert len(models) == 3
    assert [m.name for m in models] == ["alpha", "beta", "gamma"]


def test_get_aggregated_models_deduplicates_by_hash(discovery_service, mock_discovery_repo):
    """Same content_hash on different nodes should yield only one entry."""
    m1_a = _mi("llama2", content_hash="sha256:same", size_bytes=100)
    m1_b = _mi("llama2", content_hash="sha256:same", size_bytes=100)
    n1 = Node("n1", "ip1", "IDLE", [m1_a], HardwareSpec("g1", 1), [])
    n2 = Node("n2", "ip2", "IDLE", [m1_b], HardwareSpec("g1", 1), [])
    mock_discovery_repo.list_all_active_nodes.return_value = [n1, n2]

    models = discovery_service.get_aggregated_models()
    assert len(models) == 1
    assert models[0].content_hash == "sha256:same"


def test_list_peers_sorted_by_reputation(
    discovery_service, mock_discovery_repo, mock_reputation_repo
):
    """Peers should be sorted by reputation score descending."""
    n1 = _make_node("n1")
    n2 = _make_node("n2")
    n3 = _make_node("n3")

    mock_discovery_repo.list_all_active_nodes.return_value = [n1, n2, n3]

    def get_reps_batch(node_ids):
        scores = {"n1": 0.3, "n2": 0.9, "n3": 0.6}
        return [_make_reputation(nid, scores[nid]) for nid in node_ids if nid in scores]

    mock_reputation_repo.get_reputations_batch.side_effect = get_reps_batch

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

def test_sort_by_reputation_empty_list(discovery_service, mock_reputation_repo):
    """Sorting an empty list should return an empty list and not call the database."""
    result = discovery_service._sort_by_reputation([])
    assert result == []
    mock_reputation_repo.get_reputations_batch.assert_called_once_with([])


def test_sort_by_reputation_missing_reputation(discovery_service, mock_reputation_repo):
    """Nodes missing from reputation_repo should default to a score of 0.5."""
    n1 = _make_node("n1")  # Score 0.9
    n2 = _make_node("n2")  # Missing (defaults to 0.5)
    n3 = _make_node("n3")  # Score 0.2

    def get_reps_batch(node_ids):
        scores = {"n1": 0.9, "n3": 0.2}
        return [_make_reputation(nid, scores[nid]) for nid in node_ids if nid in scores]

    mock_reputation_repo.get_reputations_batch.side_effect = get_reps_batch

    result = discovery_service._sort_by_reputation([n1, n2, n3])

    assert [n.node_id for n in result] == ["n1", "n2", "n3"]
    mock_reputation_repo.get_reputations_batch.assert_called_once_with(["n1", "n2", "n3"])


def test_sort_by_reputation_stable_sort(discovery_service, mock_reputation_repo):
    """Sorting should be stable for nodes with identical scores."""
    n1 = _make_node("n1")
    n2 = _make_node("n2")
    n3 = _make_node("n3")
    n4 = _make_node("n4")

    # n1 and n2 have identical high scores.
    # n3 and n4 have identical missing/default scores.
    def get_reps_batch(node_ids):
        scores = {"n1": 0.8, "n2": 0.8}
        return [_make_reputation(nid, scores[nid]) for nid in node_ids if nid in scores]

    mock_reputation_repo.get_reputations_batch.side_effect = get_reps_batch

    result = discovery_service._sort_by_reputation([n1, n2, n3, n4])

    # Should maintain n1 before n2, and n3 before n4
    assert [n.node_id for n in result] == ["n1", "n2", "n3", "n4"]

    # Reversing original order to verify stability explicitly
    result_reversed = discovery_service._sort_by_reputation([n2, n1, n4, n3])
    assert [n.node_id for n in result_reversed] == ["n2", "n1", "n4", "n3"]
