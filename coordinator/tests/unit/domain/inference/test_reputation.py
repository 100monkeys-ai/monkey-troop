"""Unit tests for the Node Reputation domain models (ADR-0016)."""

from datetime import datetime, timezone

import pytest
from domain.inference.reputation import (NodeReputation, ReputationCalculator,
                                         ReputationComponents, ReputationScore,
                                         ReputationTier)


class TestReputationScore:
    def test_valid_score(self):
        score = ReputationScore(0.75)
        assert score.value == 0.75

    def test_boundary_zero(self):
        score = ReputationScore(0.0)
        assert score.value == 0.0

    def test_boundary_one(self):
        score = ReputationScore(1.0)
        assert score.value == 1.0

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            ReputationScore(-0.1)

    def test_above_one_raises(self):
        with pytest.raises(ValueError):
            ReputationScore(1.1)


class TestReputationComponents:
    def test_creation(self):
        components = ReputationComponents(
            availability=0.9, reliability=0.8, performance=0.7
        )
        assert components.availability == 0.9
        assert components.reliability == 0.8
        assert components.performance == 0.7

    def test_frozen(self):
        components = ReputationComponents(
            availability=0.9, reliability=0.8, performance=0.7
        )
        with pytest.raises(AttributeError):
            components.availability = 0.5


class TestReputationTier:
    def test_suspended(self):
        assert (
            ReputationTier.from_score(ReputationScore(0.0)) == ReputationTier.SUSPENDED
        )
        assert (
            ReputationTier.from_score(ReputationScore(0.19)) == ReputationTier.SUSPENDED
        )

    def test_probation(self):
        assert (
            ReputationTier.from_score(ReputationScore(0.2)) == ReputationTier.PROBATION
        )
        assert (
            ReputationTier.from_score(ReputationScore(0.39)) == ReputationTier.PROBATION
        )

    def test_standard(self):
        assert (
            ReputationTier.from_score(ReputationScore(0.4)) == ReputationTier.STANDARD
        )
        assert (
            ReputationTier.from_score(ReputationScore(0.69)) == ReputationTier.STANDARD
        )

    def test_trusted(self):
        assert ReputationTier.from_score(ReputationScore(0.7)) == ReputationTier.TRUSTED
        assert (
            ReputationTier.from_score(ReputationScore(0.89)) == ReputationTier.TRUSTED
        )

    def test_elite(self):
        assert ReputationTier.from_score(ReputationScore(0.9)) == ReputationTier.ELITE
        assert ReputationTier.from_score(ReputationScore(1.0)) == ReputationTier.ELITE


class TestReputationCalculator:
    def test_perfect_node(self):
        score, components = ReputationCalculator.calculate(
            heartbeats_received=100,
            heartbeats_expected=100,
            successful_jobs=50,
            failed_jobs=0,
            avg_throughput_ratio=1.0,
        )
        assert score.value == 1.0
        assert components.availability == 1.0
        assert components.reliability == 1.0
        assert components.performance == 1.0

    def test_poor_node(self):
        score, components = ReputationCalculator.calculate(
            heartbeats_received=0,
            heartbeats_expected=100,
            successful_jobs=0,
            failed_jobs=10,
            avg_throughput_ratio=0.0,
        )
        assert score.value == 0.0
        assert components.availability == 0.0
        assert components.reliability == 0.0
        assert components.performance == 0.0

    def test_mixed_metrics(self):
        score, components = ReputationCalculator.calculate(
            heartbeats_received=80,
            heartbeats_expected=100,
            successful_jobs=8,
            failed_jobs=2,
            avg_throughput_ratio=0.5,
        )
        # availability = 0.8, reliability = 0.8, performance = 0.5
        # weighted = 0.3*0.8 + 0.5*0.8 + 0.2*0.5 = 0.24 + 0.4 + 0.1 = 0.74
        assert score.value == 0.74
        assert components.availability == 0.8
        assert components.reliability == 0.8
        assert components.performance == 0.5

    def test_below_min_jobs_returns_default(self):
        score, components = ReputationCalculator.calculate(
            heartbeats_received=100,
            heartbeats_expected=100,
            successful_jobs=3,
            failed_jobs=0,
            avg_throughput_ratio=1.0,
        )
        assert score.value == 0.5
        assert components.availability == 1.0
        assert components.reliability == 1.0
        assert components.performance == 1.0

    def test_zero_expected_heartbeats(self):
        score, components = ReputationCalculator.calculate(
            heartbeats_received=0,
            heartbeats_expected=0,
            successful_jobs=10,
            failed_jobs=0,
            avg_throughput_ratio=1.0,
        )
        # availability defaults to 1.0 when expected is 0
        assert components.availability == 1.0
        assert score.value == 1.0

    def test_throughput_capped_at_one(self):
        score, components = ReputationCalculator.calculate(
            heartbeats_received=100,
            heartbeats_expected=100,
            successful_jobs=10,
            failed_jobs=0,
            avg_throughput_ratio=2.5,
        )
        assert components.performance == 1.0

    def test_negative_throughput_floored_at_zero(self):
        score, components = ReputationCalculator.calculate(
            heartbeats_received=100,
            heartbeats_expected=100,
            successful_jobs=10,
            failed_jobs=0,
            avg_throughput_ratio=-0.5,
        )
        assert components.performance == 0.0


class TestNodeReputation:
    def test_creation(self):
        rep = NodeReputation(
            node_id="node1",
            score=ReputationScore(0.75),
            components=ReputationComponents(
                availability=0.9, reliability=0.8, performance=0.5
            ),
            total_jobs=10,
            successful_jobs=8,
            failed_jobs=2,
            total_heartbeats_expected=100,
            total_heartbeats_received=90,
            updated_at=datetime.now(timezone.utc),
        )
        assert rep.node_id == "node1"
        assert rep.score.value == 0.75
        assert rep.total_jobs == 10
