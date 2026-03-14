"""FastAPI endpoints for the Verification (PoH) context."""

from fastapi import APIRouter, Depends, HTTPException

from application.verification_services import VerificationService
from infrastructure.dependencies import get_verification_service

from .schemas import ChallengeResponseSchema, VerifyRequestSchema

router = APIRouter(prefix="/hardware", tags=["Verification"])


@router.post("/challenge", response_model=ChallengeResponseSchema)
async def request_challenge(
    node_id: str, verification_service: VerificationService = Depends(get_verification_service)
):
    """Node requests a benchmark challenge."""
    challenge = verification_service.issue_challenge(node_id)
    return {
        "challenge_token": challenge.token,
        "seed": challenge.seed,
        "matrix_size": challenge.matrix_size,
    }


@router.post("/verify")
async def submit_proof(
    req: VerifyRequestSchema,
    verification_service: VerificationService = Depends(get_verification_service),
):
    """Node submits proof-of-hardware result."""
    result = verification_service.verify_proof(
        token=req.challenge_token,
        node_id=req.node_id,
        duration=req.duration,
        device_name=req.device_name,
        proof_hash=req.proof_hash,
    )

    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])

    return result
