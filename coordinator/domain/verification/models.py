"""Domain models for the Verification (PoH) context."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Challenge:
    """A benchmark challenge issued to a node."""

    token: str
    seed: str
    matrix_size: int
    created_at: datetime
    node_id: str

    def is_expired(self, ttl_seconds: int = 60) -> bool:
        delta = datetime.utcnow() - self.created_at
        return delta.total_seconds() > ttl_seconds


@dataclass
class BenchmarkResult:
    """The result of a completed hardware benchmark."""

    node_id: str
    duration: float
    device_name: str
    multiplier: float
    timestamp: datetime

    @staticmethod
    def calculate_multiplier(duration: float) -> float:
        """
        Baseline: RTX 3060 takes ~35s -> 1.0x
        """
        if duration <= 0:
            return 0.0

        baseline = 35.0
        multiplier = baseline / duration
        # Cap at 20x to prevent exploits
        return round(min(multiplier, 20.0), 2)
