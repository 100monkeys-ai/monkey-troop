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
