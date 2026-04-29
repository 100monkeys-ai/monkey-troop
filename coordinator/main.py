"""Monkey Troop Coordinator - DDD Entry Point."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Database and Core
from infrastructure.persistence.database import init_db

# Infrastructure Implementations
from infrastructure.security.key_repository import FileSystemKeyRepository

# Import Context-Specific Routers (Interface Layer)
from interface.api.accounting import router as accounting_router
from interface.api.inference import router as inference_router
from interface.api.security import router as security_router
from interface.api.verification import router as verification_router

# FastAPI App
app = FastAPI(title="Monkey Troop Coordinator", version="0.1.0")


def get_allowed_origins() -> list[str]:
    """Parse ALLOWED_ORIGINS from environment, filtering out wildcards."""
    raw = os.getenv("ALLOWED_ORIGINS", "")
    origins = [o.strip() for o in raw.split(",") if o.strip() and o.strip() != "*"]
    return origins if origins else ["http://localhost:3000"]


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000)
