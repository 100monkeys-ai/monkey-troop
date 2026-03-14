"""Application layer ports for the Verification (PoH) context."""

from abc import ABC, abstractmethod
from typing import Optional
from domain.verification.models import Challenge, BenchmarkResult


class ChallengeRepository(ABC):
    """Port for persistence of hardware challenges (e.g. Redis)."""

    @abstractmethod
    def save_challenge(self, challenge: Challenge, ttl_seconds: int) -> None:
        pass

    @abstractmethod
    def get_challenge(self, token: str) -> Optional[Challenge]:
        pass

    @abstractmethod
    def delete_challenge(self, token: str) -> None:
        pass


class BenchmarkRepository(ABC):
    """Port for persistence of benchmark results (e.g. PostgreSQL)."""

    @abstractmethod
    def save_result(self, result: BenchmarkResult) -> None:
        pass

    @abstractmethod
    def get_last_result(self, node_id: str) -> Optional[BenchmarkResult]:
        pass
