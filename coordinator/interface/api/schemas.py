"""Pydantic schemas for the Coordinator API."""

from typing import List, Optional

from pydantic import BaseModel


class EngineInfoSchema(BaseModel):
    type: str
    version: str
    port: int


class HardwareInfoSchema(BaseModel):
    gpu: str
    vram_free: int


class ModelIdentitySchema(BaseModel):
    name: str
    content_hash: str
    size_bytes: int


class NodeHeartbeatSchema(BaseModel):
    node_id: str
    tailscale_ip: str
    status: str
    models: List[ModelIdentitySchema]
    hardware: HardwareInfoSchema
    engines: List[EngineInfoSchema]
    encryption_public_key: Optional[str] = None


class ChallengeResponseSchema(BaseModel):
    challenge_token: str
    seed: str
    matrix_size: int


class VerifyRequestSchema(BaseModel):
    node_id: str
    challenge_token: str
    proof_hash: str
    duration: float
    device_name: str


class AuthorizeRequestSchema(BaseModel):
    model: str
    requester: str


class AuthorizeResponseSchema(BaseModel):
    target_ip: str
    token: str
    estimated_cost: int
    encryption_public_key: Optional[str] = None


class BalanceResponseSchema(BaseModel):
    public_key: str
    balance_seconds: int
    balance_hours: float


class TransactionSchema(BaseModel):
    id: Optional[int]
    requester: Optional[str]
    worker: Optional[str]
    credits: float
    duration: Optional[int]
    timestamp: str
    type: str


class ReputationComponentsSchema(BaseModel):
    availability: float
    reliability: float
    performance: float


class NodeReputationSchema(BaseModel):
    node_id: str
    score: float
    tier: str
    components: ReputationComponentsSchema
    total_jobs: int
    successful_jobs: int
    failed_jobs: int
    updated_at: str
