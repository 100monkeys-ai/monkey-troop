"""Monkey Troop Coordinator - DDD Entry Point."""

import os
import random
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from redis import Redis

# Database and Core
from database import get_db, init_db

# Infrastructure Implementations
from infrastructure.persistence.repositories import SqlAlchemyUserRepository, SqlAlchemyTransactionRepository
from infrastructure.persistence.inference_repositories import RedisNodeDiscoveryRepository
from infrastructure.persistence.verification_repositories import RedisChallengeRepository, SqlAlchemyBenchmarkRepository
from infrastructure.security.key_repository import FileSystemKeyRepository
from infrastructure.security.token_service import JoseJwtTokenService

# Application Services
from application.accounting_services import AccountingService
from application.inference_services import DiscoveryService
from application.verification_services import VerificationService
from application.security_services import SecurityService

# Redis Client
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_client = Redis(host=redis_host, port=6379, db=0, decode_responses=True)

# Dependency Injection Providers
def get_accounting_service(db: Session = Depends(get_db)) -> AccountingService:
    return AccountingService(SqlAlchemyUserRepository(db), SqlAlchemyTransactionRepository(db))

def get_discovery_service() -> DiscoveryService:
    return DiscoveryService(RedisNodeDiscoveryRepository(redis_client))

def get_verification_service(db: Session = Depends(get_db)) -> VerificationService:
    return VerificationService(RedisChallengeRepository(redis_client), SqlAlchemyBenchmarkRepository(db))

def get_security_service() -> SecurityService:
    key_repo = FileSystemKeyRepository()
    token_service = JoseJwtTokenService(key_repo)
    return SecurityService(token_service, key_repo)

# FastAPI App
app = FastAPI(title="Monkey Troop Coordinator", version="0.1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and Mount Context-Specific Routers (Interface Layer)
from interface.api.accounting import router as accounting_router
from interface.api.inference import router as inference_router
from interface.api.verification import router as verification_router
from interface.api.security import router as security_router
from interface.api.schemas import AuthorizeRequestSchema, AuthorizeResponseSchema

app.include_router(accounting_router)
app.include_router(inference_router)
app.include_router(verification_router)
app.include_router(security_router)

@app.on_event("startup")
async def startup_event():
    key_repo = FileSystemKeyRepository()
    key_repo.ensure_keys_exist()
    init_db()

@app.get("/health")
async def health():
    return {"status": "healthy"}

# Orchestrated Endpoint: Authorization (Involves multiple contexts)
@app.post("/authorize", response_model=AuthorizeResponseSchema)
async def authorize_request(
    req: AuthorizeRequestSchema, 
    request: Request,
    db: Session = Depends(get_db),
    accounting_service: AccountingService = Depends(get_accounting_service),
    discovery_service: DiscoveryService = Depends(get_discovery_service),
    security_service: SecurityService = Depends(get_security_service)
):
    """Orchestrated endpoint: Authorize a request across multiple contexts."""
    
    # 1. Accounting: Ensure user has balance
    user = accounting_service.create_user_if_not_exists(req.requester)
    # Reservation logic simplified for MVP
    if user.balance.seconds < 300:
        raise HTTPException(status_code=402, detail="Insufficient credits")

    # 2. Inference: Discovery an idle node
    selected_node = discovery_service.select_node_for_model(req.model)
    if not selected_node:
        raise HTTPException(status_code=503, detail=f"No idle nodes found for model: {req.model}")

    # 3. Security: Issue a signed ticket
    ticket = security_service.issue_authorization_ticket(req.requester, selected_node.node_id)

    return {
        "target_ip": selected_node.tailscale_ip,
        "token": ticket.token,
        "estimated_cost": 300
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
