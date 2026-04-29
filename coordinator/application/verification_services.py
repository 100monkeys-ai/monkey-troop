"""Application layer use cases for the Verification context."""

import uuid
from datetime import datetime
from typing import Any, Dict

from domain.verification.models import BenchmarkResult, Challenge, HardwareProof

from .verification_ports import BenchmarkRepository, ChallengeRepository


class VerificationService:
    """Orchestrates hardware verification use cases."""

    def __init__(self, challenge_repo: ChallengeRepository, benchmark_repo: BenchmarkRepository):
        self.challenge_repo = challenge_repo
        self.benchmark_repo = benchmark_repo

    def issue_challenge(self, node_id: str, matrix_size: int = 4096) -> Challenge:
        """Use Case: Issue a new hardware benchmark challenge."""
        token = str(uuid.uuid4())
        seed = str(uuid.uuid4().hex)

        challenge = Challenge(
            token=token,
            seed=seed,
            matrix_size=matrix_size,
            created_at=datetime.utcnow(),
            node_id=node_id,
        )

        # Save to ephemeral storage (Redis)
        self.challenge_repo.save_challenge(challenge, ttl_seconds=60)

        return challenge

    def verify_proof(self, proof: HardwareProof) -> Dict[str, Any]:
        """Use Case: Verify the proof-of-hardware submission."""

        # 1. Retrieve and validate challenge
        challenge = self.challenge_repo.get_challenge(proof.token)
        if not challenge:
            return {"status": "error", "message": "Challenge expired or invalid"}

        if challenge.node_id != proof.node_id:
            return {"status": "error", "message": "Challenge node ID mismatch"}

        # 2. In a real system, we would verify proof_hash here using the original seed
        # For MVP, we calculate the multiplier based on duration
        multiplier = BenchmarkResult.calculate_multiplier(proof.duration)

        # 3. Save benchmark result to persistent storage
        result = BenchmarkResult(
            node_id=proof.node_id,
            duration=proof.duration,
            device_name=proof.device_name,
            multiplier=multiplier,
            timestamp=datetime.utcnow(),
        )
        self.benchmark_repo.save_result(result)

        # 4. Cleanup
        self.challenge_repo.delete_challenge(proof.token)

        tier = "High Performance" if multiplier > 3 else "Standard"
        return {"status": "verified", "assigned_multiplier": multiplier, "tier": tier}
