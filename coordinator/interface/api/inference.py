"""FastAPI endpoints for the Inference context."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from application.inference_services import DiscoveryService
from domain.inference.models import Node, HardwareSpec, EngineInfo
from .schemas import NodeHeartbeatSchema
from main import get_discovery_service

router = APIRouter(tags=["Inference"])

@router.post("/heartbeat")
async def receive_heartbeat(
    data: NodeHeartbeatSchema,
    discovery_service: DiscoveryService = Depends(get_discovery_service)
):
    """Update node status and model availability."""
    node = Node(
        node_id=data.node_id,
        tailscale_ip=data.tailscale_ip,
        status=data.status,
        models=data.models,
        hardware=HardwareSpec(
            gpu=data.hardware.gpu,
            vram_free_mb=data.hardware.vram_free
        ),
        engines=[
            EngineInfo(e.type, e.version, e.port)
            for e in data.engines
        ]
    )
    
    discovery_service.register_heartbeat(node)
    return {"status": "seen"}

@router.get("/peers")
async def list_peers(
    model: Optional[str] = Query(None),
    discovery_service: DiscoveryService = Depends(get_discovery_service)
):
    """List available nodes, optionally filtered by model."""
    nodes = discovery_service.list_peers(model)
    return {
        "count": len(nodes),
        "nodes": [json.loads(n.to_json()) for n in nodes]
    }

@router.get("/v1/models")
async def list_models_openai(
    discovery_service: DiscoveryService = Depends(get_discovery_service)
):
    """OpenAI-compatible models endpoint."""
    models = discovery_service.get_aggregated_models()
    return {
        "object": "list",
        "data": [
            {"id": m, "object": "model", "owned_by": "monkey-troop"} 
            for m in models
        ],
    }

import json # For to_json use in list_peers
