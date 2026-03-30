from unittest.mock import MagicMock

import pytest

from coordinator.application.inference_services import DiscoveryService
from coordinator.domain.inference.models import HardwareSpec, ModelIdentity, Node


def _mi(name: str, content_hash: str = "sha256:default", size_bytes: int = 1000) -> ModelIdentity:
    return ModelIdentity(name=name, content_hash=content_hash, size_bytes=size_bytes)


@pytest.fixture
def mock_discovery_repo():
    return MagicMock()


@pytest.fixture
def discovery_service(mock_discovery_repo):
    return DiscoveryService(mock_discovery_repo)


def test_register_heartbeat(discovery_service, mock_discovery_repo):
    node = Node(
        node_id="node1",
        tailscale_ip="100.1.1.1",
        status="IDLE",
        models=[_mi("llama2")],
        hardware=HardwareSpec("GPU", 1000),
        engines=[],
    )
    discovery_service.register_heartbeat(node, ttl_seconds=20)
    mock_discovery_repo.save_node.assert_called_once_with(node, 20)


def test_select_node_for_model_by_name(discovery_service, mock_discovery_repo):
    node1 = Node("n1", "ip1", "IDLE", [_mi("m1")], HardwareSpec("g1", 1), [])
    node2 = Node("n2", "ip2", "BUSY", [_mi("m1")], HardwareSpec("g1", 1), [])

    mock_discovery_repo.find_nodes_by_model.return_value = [node1, node2]

    selected = discovery_service.select_node_for_model("m1")
    assert selected == node1
    mock_discovery_repo.find_nodes_by_model.assert_called_once_with("m1")


def test_select_node_for_model_by_hash(discovery_service, mock_discovery_repo):
    node1 = Node(
        "n1", "ip1", "IDLE", [_mi("m1", content_hash="sha256:abc")], HardwareSpec("g1", 1), []
    )
    mock_discovery_repo.find_nodes_by_model.return_value = [node1]

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


def test_list_peers_with_model(discovery_service, mock_discovery_repo):
    discovery_service.list_peers(model="m1")
    mock_discovery_repo.find_nodes_by_model.assert_called_once_with("m1")


def test_list_peers_without_model(discovery_service, mock_discovery_repo):
    discovery_service.list_peers()
    mock_discovery_repo.list_all_active_nodes.assert_called_once()
