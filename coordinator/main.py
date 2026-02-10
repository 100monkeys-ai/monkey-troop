"""Main FastAPI application for Monkey Troop Coordinator."""

import os
import uuid
import json
import random
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy.orm import Session

from database import init_db, get_db, Node, User
from auth import create_jwt_ticket
from crypto import ensure_keys_exist, get_public_key_string
from transactions import (
    create_user_if_not_exists, get_user_balance, check_sufficient_balance,
    reserve_credits, record_job_completion, get_transaction_history,
    generate_receipt_signature
)
from rate_limit import RateLimiter
from middleware import RateLimitMiddleware, RequestTracingMiddleware
from timeout_middleware import TimeoutMiddleware
import audit
from secrets import compare_digest
from fastapi.security import HTTPBasic, HTTPBasicCredentials

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

# Rate limiter (order matters - outermost first)
app.add_middleware(TimeoutMiddleware)
# Add timeout middleware (outermost layer)
app.add_middleware(TimeoutMiddleware)

# Add request tracing and rate limiting
app.add_middleware(RequestTracingMiddleware)
app.add_middleware(RateLimitMiddleware, rate_limiter=rate_limiter)

# HTTP Basic Auth for admin endpoints
security = HTTPBasic()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me-in-production")

# Constants
CHALLENGE_TTL = 60  # Challenge expires in 60 seconds
HEARTBEAT_TTL = 15  # Node heartbeat expires in 15 seconds
ESTIMATED_JOB_DURATION = 300  # 5 minutes default reservation


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
    engines: list[EngineInfo]


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
    estimated_cost: int


class JobReceiptRequest(BaseModel):
    job_id: str
    requester_public_key: str
    worker_node_id: str
    duration_seconds: int
    signature: str


class BalanceResponse(BaseModel):
    public_key: str
    balance_seconds: int
    balance_hours: float


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
def run_migrations():
    """Run database migrations using Alembic"""
    try:
        from alembic.config import Config
        from alembic import command
        
        # Run migrations
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        print("✓ Database migrations applied")
    except Exception as e:
        print(f"⚠️  Migration error: {e}")
        print("Creating tables directly...")
        from database import Base, engine
        Base.metadata.create_all(bind=engine)

@app.on_event("startup")
async def startup_event():
    """Initialize database and keys on startup."""
    ensure_keys_exist()
    run_migrations()
    init_db()
    print("🐒 Monkey Troop Coordinator started")


# ----------------------
# HEALTH CHECK
# ----------------------
@app.get("/health")
async def health_check():
    """Health check endpoint."""


@app.get("/public-key")
async def get_public_key():
    """
    Expose RSA public key for JWT verification.
    Workers fetch this on startup to verify tickets.
    """
    return {"public_key": get_public_key_string()}
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
        raw_nodes = redis_client.mget(keys)
        for raw_data in raw_nodes:
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
async def authorize_request(
    req: AuthorizeRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Client requests authorization to use a node.
    Returns JWT ticket and target node IP.
    """
    client_ip = request.client.host if request.client else "unknown"
    
    # Create user if doesn't exist (gets starter credits)
    user = create_user_if_not_exists(db, req.requester)
    
    # Check sufficient balance
    if not check_sufficient_balance(db, req.requester, ESTIMATED_JOB_DURATION):
        audit.log_authorization(
            req.requester, req.model, "none",
            client_ip, False, "insufficient_credits"
        )
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits. Balance: {user.balance_seconds}s, Required: {ESTIMATED_JOB_DURATION}s"
        )
    
    # Find available nodes with requested model
    keys = redis_client.keys("node:*")
    candidates = []
    
    if keys:
        raw_nodes = redis_client.mget(keys)
        for raw_data in raw_nodes:
            if raw_data:
                node = json.loads(raw_data)
                if node.get("status") == "IDLE" and req.model in node.get("models", []):
                    candidates.append(node)
    
    if not candidates:
        audit.log_authorization(
            req.requester, req.model, "none",
            client_ip, False, "no_nodes_available"
        )
        raise HTTPException(
            status_code=503,
            detail=f"No idle nodes found for model: {req.model}"
        )
    
    # Simple random selection (can be upgraded to load balancing)
    selected = random.choice(candidates)
    
    # Reserve credits for job
    if not reserve_credits(db, req.requester, ESTIMATED_JOB_DURATION):
        raise HTTPException(status_code=402, detail="Failed to reserve credits")
    
    # Create JWT ticket
    token = create_jwt_ticket(
        user_id=req.requester,
        target_node_id=selected["node_id"],
        project="free-tier"
    )
    
    audit.log_authorization(
        req.requester, req.model, selected["node_id"],
        client_ip, True, None
    )
    
    print(f"🎫 Authorized {req.requester} to use {selected['node_id']} ({selected['tailscale_ip']})")
    
    return {
        "target_ip": selected["tailscale_ip"],
        "token": token,
        "estimated_cost": ESTIMATED_JOB_DURATION
    }


@app.post("/transactions/submit")
async def submit_job_completion(
    receipt: JobReceiptRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Worker submits job completion receipt for credit transfer."""
    client_ip = request.client.host if request.client else "unknown"
    
    result = record_job_completion(
        db=db,
        job_id=receipt.job_id,
        requester_public_key=receipt.requester_public_key,
        worker_node_id=receipt.worker_node_id,
        duration_seconds=receipt.duration_seconds,
        receipt_signature=receipt.signature
    )
    
    if result["status"] == "success":
        audit.log_transaction(
            receipt.job_id,
            receipt.requester_public_key,
            receipt.worker_node_id,
            receipt.duration_seconds,
            result["credits_transferred"],
            client_ip
        )
    else:
        audit.log_security_event(
            "invalid_receipt",
            {"job_id": receipt.job_id, "reason": result.get("message")},
            client_ip
        )
    
    return result


@app.get("/users/{public_key}/balance")
async def get_balance(public_key: str, db: Session = Depends(get_db)):
    """Get user's credit balance."""
    balance = get_user_balance(db, public_key)
    return {
        "public_key": public_key,
        "balance_seconds": balance,
        "balance_hours": round(balance / 3600, 2)
    }


@app.get("/users/{public_key}/transactions")
async def get_transactions(
    public_key: str,
    limit: int = 50,
):
    """Get transaction history for a user."""
    from transactions import get_transaction_history
    return {"transactions": get_transaction_history(public_key, limit)}


@app.get("/admin/audit")
async def get_audit_logs_endpoint(
    credentials: HTTPBasicCredentials = Depends(security),
    limit: int = 100,
    offset: int = 0,
    event_type: Optional[str] = None,
    user_id: Optional[str] = None
):
    """
    Get audit logs (admin only, requires HTTP Basic Auth).
    
    Query parameters:
    - limit: Number of records to return (default 100)
    - offset: Number of records to skip (default 0)
    - event_type: Filter by event type (authorization, transaction, rate_limit, security)
    - user_id: Filter by user ID
    """
    # Verify password
    if not compare_digest(credentials.password, ADMIN_PASSWORD):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"}
        )
    
    logs = audit.get_audit_logs(
        limit=min(limit, 1000),  # Cap at 1000
        offset=offset,
        event_type=event_type,
        user_id=user_id
    )
    
    return {
        "logs": logs,
        "count": len(logs),
        "limit": limit,
        "offset": offset
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
    
    if keys:
        raw_nodes = redis_client.mget(keys)
        for raw_data in raw_nodes:
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
