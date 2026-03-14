"""Application layer use cases for the Verification context."""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from domain.verification.models import Challenge, BenchmarkResult
from .verification_ports import ChallengeRepository, BenchmarkRepository


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
            node_id=node_id
        )
        
        # Save to ephemeral storage (Redis)
        self.challenge_repo.save_challenge(challenge, ttl_seconds=60)
        
        return challenge

    def verify_proof(
        self, 
        token: str, 
        node_id: str, 
        duration: float, 
        device_name: str, 
        proof_hash: str
    ) -> Dict[str, Any]:
        """Use Case: Verify the proof-of-hardware submission."""
        
        # 1. Retrieve and validate challenge
        challenge = self.challenge_repo.get_challenge(token)
        if not challenge:
            return {"status": "error", "message": "Challenge expired or invalid"}

        if challenge.node_id != node_id:
            return {"status": "error", "message": "Challenge node ID mismatch"}

        # 2. In a real system, we would verify proof_hash here using the original seed
        # For MVP, we calculate the multiplier based on duration
        multiplier = BenchmarkResult.calculate_multiplier(duration)

        # 3. Save benchmark result to persistent storage
        result = BenchmarkResult(
            node_id=node_id,
            duration=duration,
            device_name=device_name,
            multiplier=multiplier,
            timestamp=datetime.utcnow()
        )
        self.benchmark_repo.save_result(result)

        # 4. Cleanup
        self.challenge_repo.delete_challenge(token)

        tier = "High Performance" if multiplier > 3 else "Standard"
        return {
            "status": "verified",
            "assigned_multiplier": multiplier,
            "tier": tier
        }
