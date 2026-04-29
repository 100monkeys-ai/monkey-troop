"""FastAPI endpoints for the Inference context."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from application.inference_services import DiscoveryService
from application.orchestration_services import OrchestrationService
from domain.inference.models import EngineInfo, HardwareSpec, ModelIdentity, Node
from domain.inference.reputation import ReputationTier
from infrastructure.dependencies import get_discovery_service, get_orchestration_service

from .schemas import (
    AuthorizeRequestSchema,
    AuthorizeResponseSchema,
    NodeHeartbeatSchema,
    NodeReputationSchema,
    ReputationComponentsSchema,
)

router = APIRouter(tags=["Inference"])


@router.post("/authorize", response_model=AuthorizeResponseSchema)
async def authorize_request(
    req: AuthorizeRequestSchema,
    orchestration_service: OrchestrationService = Depends(get_orchestration_service),
):
    """Orchestrated endpoint: Authorize a request across multiple contexts."""
    from application.orchestration_services import InsufficientCreditsError, NoNodesAvailableError

    try:
        result = orchestration_service.authorize_inference(req.requester, req.model)
    except InsufficientCreditsError as e:
        raise HTTPException(status_code=402, detail=str(e))
    except NoNodesAvailableError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return {
        "target_ip": result.target_ip,
        "token": result.token,
        "estimated_cost": result.estimated_cost,
        "encryption_public_key": result.encryption_public_key,
    }


@router.post("/heartbeat")
async def receive_heartbeat(
    data: NodeHeartbeatSchema, discovery_service: DiscoveryService = Depends(get_discovery_service)
):
    """Update node status and model availability."""
    node = Node(
        node_id=data.node_id,
        tailscale_ip=data.tailscale_ip,
        status=data.status,
        models=[
            ModelIdentity(name=m.name, content_hash=m.content_hash, size_bytes=m.size_bytes)
            for m in data.models
        ],
        hardware=HardwareSpec(gpu=data.hardware.gpu, vram_free_mb=data.hardware.vram_free),
        engines=[EngineInfo(e.type, e.version, e.port) for e in data.engines],
        encryption_public_key=data.encryption_public_key,
    )

    discovery_service.register_heartbeat(node)
    return {"status": "seen"}


@router.get("/peers")
async def list_peers(
    model: Optional[str] = Query(None),
    discovery_service: DiscoveryService = Depends(get_discovery_service),
):
    """List available nodes sorted by reputation, optionally filtered by model."""
    nodes = discovery_service.list_peers(model)
    nodes_data = [n.to_dict() for n in nodes]
    return {"count": len(nodes), "nodes": nodes_data}


@router.get("/nodes/{node_id}/reputation", response_model=NodeReputationSchema)
async def get_node_reputation(
    node_id: str,
    discovery_service: DiscoveryService = Depends(get_discovery_service),
):
    """Get detailed reputation breakdown for a specific node."""
    rep = discovery_service.reputation_repo.get_reputation(node_id)
    if not rep:
        raise HTTPException(status_code=404, detail="Node reputation not found")

    tier = ReputationTier.from_score(rep.score)
    return NodeReputationSchema(
        node_id=rep.node_id,
        score=rep.score.value,
        tier=tier.value,
        components=ReputationComponentsSchema(
            availability=rep.components.availability,
            reliability=rep.components.reliability,
            performance=rep.components.performance,
        ),
        total_jobs=rep.total_jobs,
        successful_jobs=rep.successful_jobs,
        failed_jobs=rep.failed_jobs,
        updated_at=rep.updated_at.isoformat(),
    )


@router.get("/v1/models")
async def list_models_openai(discovery_service: DiscoveryService = Depends(get_discovery_service)):
    """OpenAI-compatible models endpoint."""
    models = discovery_service.get_aggregated_models()
    return {
        "object": "list",
        "data": [
            {
                "id": m.name,
                "object": "model",
                "owned_by": "monkey-troop",
                "content_hash": m.content_hash,
                "size_bytes": m.size_bytes,
            }
            for m in models
        ],
    }
