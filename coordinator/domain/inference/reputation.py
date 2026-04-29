"""Domain models for the Node Reputation system (ADR-0016)."""

import enum
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ReputationScore:
    """Value object representing a node's composite reputation score."""

    value: float

    def __post_init__(self):
        if not (0.0 <= self.value <= 1.0):
            raise ValueError(
                f"Reputation score must be between 0.0 and 1.0, got {self.value}"
            )


@dataclass(frozen=True)
class ReputationComponents:
    """Value object holding the individual factors that compose a reputation score."""

    availability: float  # 0.0-1.0: uptime ratio from heartbeat consistency
    reliability: float  # 0.0-1.0: job success rate
    performance: float  # 0.0-1.0: actual throughput vs expected


class ReputationTier(str, enum.Enum):
    """Tier classification based on reputation score."""

    SUSPENDED = "suspended"  # score < 0.2
    PROBATION = "probation"  # 0.2 <= score < 0.4
    STANDARD = "standard"  # 0.4 <= score < 0.7
    TRUSTED = "trusted"  # 0.7 <= score < 0.9
    ELITE = "elite"  # score >= 0.9

    @staticmethod
    def from_score(score: ReputationScore) -> "ReputationTier":
        if score.value < 0.2:
            return ReputationTier.SUSPENDED
        elif score.value < 0.4:
            return ReputationTier.PROBATION
        elif score.value < 0.7:
            return ReputationTier.STANDARD
        elif score.value < 0.9:
            return ReputationTier.TRUSTED
        else:
            return ReputationTier.ELITE


@dataclass
class NodeReputation:
    """Entity tracking a node's reputation over time."""

    node_id: str
    score: ReputationScore
    components: ReputationComponents
    total_jobs: int
    successful_jobs: int
    failed_jobs: int
    total_heartbeats_expected: int
    total_heartbeats_received: int
    updated_at: datetime


class ReputationCalculator:
    """Domain service that computes reputation scores from raw metrics."""

    AVAILABILITY_WEIGHT = 0.3
    RELIABILITY_WEIGHT = 0.5
    PERFORMANCE_WEIGHT = 0.2

    MIN_JOBS_FOR_REPUTATION = 5
    DEFAULT_SCORE = ReputationScore(0.5)
    DEFAULT_COMPONENTS = ReputationComponents(
        availability=1.0, reliability=1.0, performance=1.0
    )

    @staticmethod
    def calculate(
        heartbeats_received: int,
        heartbeats_expected: int,
        successful_jobs: int,
        failed_jobs: int,
        avg_throughput_ratio: float,
    ) -> tuple:
        """Calculate reputation score and components from raw metrics.

        Returns a tuple of (ReputationScore, ReputationComponents).
        """
        total_jobs = successful_jobs + failed_jobs

        if total_jobs < ReputationCalculator.MIN_JOBS_FOR_REPUTATION:
            return (
                ReputationCalculator.DEFAULT_SCORE,
                ReputationCalculator.DEFAULT_COMPONENTS,
            )

        # Availability: heartbeat consistency
        if heartbeats_expected > 0:
            availability = min(heartbeats_received / heartbeats_expected, 1.0)
        else:
            availability = 1.0

        # Reliability: job success rate
        reliability = successful_jobs / total_jobs

        # Performance: throughput ratio capped at 1.0
        performance = min(max(avg_throughput_ratio, 0.0), 1.0)

        weighted_score = (
            ReputationCalculator.AVAILABILITY_WEIGHT * availability
            + ReputationCalculator.RELIABILITY_WEIGHT * reliability
            + ReputationCalculator.PERFORMANCE_WEIGHT * performance
        )
        clamped_score = max(0.0, min(weighted_score, 1.0))

        return (
            ReputationScore(round(clamped_score, 4)),
            ReputationComponents(
                availability=round(availability, 4),
                reliability=round(reliability, 4),
                performance=round(performance, 4),
            ),
        )
