"""Dependency injection providers for Monkey Troop Coordinator."""

import os

from fastapi import Depends
from redis import Redis
from sqlalchemy.orm import Session

# Application Services
from application.accounting_services import AccountingService
from application.inference_services import DiscoveryService
from application.orchestration_services import OrchestrationService
from application.security_services import SecurityService
from application.verification_services import VerificationService
from infrastructure.persistence.inference_repositories import RedisNodeDiscoveryRepository

# Infrastructure Implementations
from infrastructure.persistence.repositories import (
    SqlAlchemyTransactionRepository,
    SqlAlchemyUserRepository,
)
from infrastructure.persistence.verification_repositories import (
    RedisChallengeRepository,
    SqlAlchemyBenchmarkRepository,
)
from infrastructure.security.key_repository import FileSystemKeyRepository
from infrastructure.security.token_service import JoseJwtTokenService

# Database and Core
from .persistence.database import get_db

# Redis Client
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_client = Redis(host=redis_host, port=6379, db=0, decode_responses=True)


def get_redis_client() -> Redis:
    return redis_client


# Dependency Injection Providers
def get_accounting_service(db: Session = Depends(get_db)) -> AccountingService:
    return AccountingService(SqlAlchemyUserRepository(db), SqlAlchemyTransactionRepository(db))


def get_discovery_service(redis: Redis = Depends(get_redis_client)) -> DiscoveryService:
    return DiscoveryService(RedisNodeDiscoveryRepository(redis))


def get_verification_service(
    db: Session = Depends(get_db), redis: Redis = Depends(get_redis_client)
) -> VerificationService:
    return VerificationService(RedisChallengeRepository(redis), SqlAlchemyBenchmarkRepository(db))


def get_security_service() -> SecurityService:
    key_repo = FileSystemKeyRepository()
    token_service = JoseJwtTokenService(key_repo)
    return SecurityService(token_service, key_repo)


def get_orchestration_service(
    accounting_service: AccountingService = Depends(get_accounting_service),
    discovery_service: DiscoveryService = Depends(get_discovery_service),
    security_service: SecurityService = Depends(get_security_service),
) -> OrchestrationService:
    return OrchestrationService(accounting_service, discovery_service, security_service)
