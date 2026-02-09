"""Main FastAPI application for Monkey Troop Coordinator."""

import os
import uuid
import json
import random
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
from sqlalchemy.orm import Session

from database import init_db, get_db, Node, User
from auth import create_jwt_ticket

app = FastAPI(
    title="Monkey Troop Coordinator",
    description="Discovery and verification service for distributed AI compute",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis connection
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_client = Redis(host=redis_host, port=6379, db=0, decode_responses=True)

# Constants
CHALLENGE_TTL = 60  # Challenge expires in 60 seconds
HEARTBEAT_TTL = 15  # Node heartbeat expires in 15 seconds


# ----------------------
# DATA MODELS (Pydantic)
# ----------------------
from pydantic import BaseModel


class EngineInfo(BaseModel):
    type: str
    version: str
    port: int


class HardwareInfo(BaseModel):
    gpu: str
    vram_free: int


class NodeHeartbeat(BaseModel):
    node_id: str
    tailscale_ip: str
    status: str  # "IDLE", "BUSY", "OFFLINE"
    models: list[str]
    hardware: HardwareInfo
    engine: EngineInfo


class ChallengeRequest(BaseModel):
    node_id: str


class ChallengeResponse(BaseModel):
    challenge_token: str
    seed: str
    matrix_size: int


class VerifyRequest(BaseModel):
    node_id: str
    challenge_token: str
    proof_hash: str
    duration: float
    device_name: str


class VerifyResponse(BaseModel):
    status: str
    assigned_multiplier: float
    tier: str


class AuthorizeRequest(BaseModel):
    model: str
    requester: str


class AuthorizeResponse(BaseModel):
    target_ip: str
    token: str


class PeersResponse(BaseModel):
    count: int
    nodes: list[dict]


# ----------------------
# HELPER FUNCTIONS
# ----------------------
def calculate_multiplier(duration: float) -> float:
    """
    Calculate hardware multiplier based on benchmark duration.
    Baseline: RTX 3060 takes ~35s -> 1.0x
    """
    if duration <= 0:
        return 0.0
    
    baseline = 35.0
    multiplier = baseline / duration
    
    # Cap at 20x to prevent exploits
    return round(min(multiplier, 20.0), 2)


# ----------------------
# STARTUP/SHUTDOWN
# ----------------------
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()
    print("🐒 Monkey Troop Coordinator started")


# ----------------------
# HEALTH CHECK
# ----------------------
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "monkey-troop-coordinator"}


# ----------------------
# NODE REGISTRATION
# ----------------------
@app.post("/heartbeat")
async def receive_heartbeat(data: NodeHeartbeat):
    """
    Workers send heartbeat every 10 seconds.
    Store in Redis with 15-second TTL for automatic cleanup.
    """
    key = f"node:{data.node_id}"
    
    # Store node data
    redis_client.set(key, data.model_dump_json())
    redis_client.expire(key, HEARTBEAT_TTL)
    
    return {"status": "seen"}


# ----------------------
# PEER DISCOVERY
# ----------------------
@app.get("/peers", response_model=PeersResponse)
async def list_peers(model: Optional[str] = None):
    """
    List available nodes, optionally filtered by model.
    """
    keys = redis_client.keys("node:*")
    nodes = []
    
    if keys:
        for key in keys:
            raw_data = redis_client.get(key)
            if raw_data:
                node = json.loads(raw_data)
                
                # Filter by status
                if node.get("status") != "IDLE":
                    continue
                
                # Filter by model if requested
                if model and model not in node.get("models", []):
                    continue
                
                nodes.append(node)
    
    return {"count": len(nodes), "nodes": nodes}


# ----------------------
# PROOF OF HARDWARE
# ----------------------
@app.post("/hardware/challenge", response_model=ChallengeResponse)
async def request_challenge(req: ChallengeRequest, db: Session = Depends(get_db)):
    """
    Node requests a benchmark challenge.
    Generate random seed and store in Redis.
    """
    seed = uuid.uuid4().hex
    token = uuid.uuid4().hex
    
    # Store challenge in Redis with expiration
    redis_client.setex(f"challenge:{token}", CHALLENGE_TTL, seed)
    
    print(f"📊 Issued challenge to {req.node_id}: {seed}")
    
    return {
        "challenge_token": token,
        "seed": seed,
        "matrix_size": 4096
    }


@app.post("/hardware/verify", response_model=VerifyResponse)
async def submit_proof(req: VerifyRequest, db: Session = Depends(get_db)):
    """
    Node submits proof-of-hardware result.
    Verify and assign multiplier.
    """
    # Retrieve original seed
    original_seed = redis_client.get(f"challenge:{req.challenge_token}")
    
    if not original_seed:
        raise HTTPException(status_code=400, detail="Challenge expired or invalid")
    
    # Basic validation
    if len(req.proof_hash) != 64:
        raise HTTPException(status_code=400, detail="Invalid hash format")
    
    # Calculate score
    score = calculate_multiplier(req.duration)
    
    # Update or create node in database
    node = db.query(Node).filter(Node.node_id == req.node_id).first()
    
    if not node:
        # Auto-register node (in production, require explicit registration)
        # For now, assign to a default user
        default_user = db.query(User).first()
        if not default_user:
            # Create default user
            default_user = User(
                username="system",
                public_key="system-key",
                balance_seconds=0
            )
            db.add(default_user)
            db.commit()
        
        node = Node(
            node_id=req.node_id,
            owner_id=default_user.id
        )
        db.add(node)
    
    node.multiplier = score
    node.hardware_model = req.device_name
    node.benchmark_score = req.duration
    node.last_benchmark = datetime.utcnow()
    
    db.commit()
    
    # Cleanup
    redis_client.delete(f"challenge:{req.challenge_token}")
    
    tier = "High Performance" if score > 3 else "Standard"
    print(f"✅ Verified {req.node_id}. Time: {req.duration}s. Score: {score}x ({tier})")
    
    return {
        "status": "verified",
        "assigned_multiplier": score,
        "tier": tier
    }


# ----------------------
# AUTHORIZATION
# ----------------------
@app.post("/authorize", response_model=AuthorizeResponse)
async def authorize_request(req: AuthorizeRequest, db: Session = Depends(get_db)):
    """
    Client requests authorization to use a node.
    Returns JWT ticket and target node IP.
    """
    # Find available nodes with requested model
    keys = redis_client.keys("node:*")
    candidates = []
    
    for key in keys:
        raw_data = redis_client.get(key)
        if raw_data:
            node = json.loads(raw_data)
            if node.get("status") == "IDLE" and req.model in node.get("models", []):
                candidates.append(node)
    
    if not candidates:
        raise HTTPException(
            status_code=503,
            detail=f"No idle nodes found for model: {req.model}"
        )
    
    # Simple random selection (can be upgraded to load balancing)
    selected = random.choice(candidates)
    
    # Create JWT ticket
    token = create_jwt_ticket(
        user_id=req.requester,
        target_node_id=selected["node_id"],
        project="free-tier"
    )
    
    print(f"🎫 Authorized {req.requester} to use {selected['node_id']} ({selected['tailscale_ip']})")
    
    return {
        "target_ip": selected["tailscale_ip"],
        "token": token
    }


# ----------------------
# OPENAI COMPATIBILITY
# ----------------------
@app.get("/v1/models")
async def list_models():
    """
    OpenAI-compatible models endpoint.
    Aggregates all models from active nodes.
    """
    keys = redis_client.keys("node:*")
    unique_models = set()
    
    for key in keys:
        raw_data = redis_client.get(key)
        if raw_data:
            node = json.loads(raw_data)
            unique_models.update(node.get("models", []))
    
    return {
        "object": "list",
        "data": [
            {"id": m, "object": "model", "owned_by": "monkey-troop"}
            for m in sorted(unique_models)
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
