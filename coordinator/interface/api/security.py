"""FastAPI endpoints for the Security & Identity context."""

from fastapi import APIRouter, Depends

from application.security_services import SecurityService
from infrastructure.dependencies import get_security_service

router = APIRouter(tags=["Security"])


@router.get("/public-key")
async def get_public_key(security_service: SecurityService = Depends(get_security_service)):
    """Expose RSA public key for Workers to verify JWTs."""
    return {"public_key": security_service.get_public_key_for_distribution()}
