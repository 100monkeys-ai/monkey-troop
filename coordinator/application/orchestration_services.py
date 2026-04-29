"""Application layer use cases for orchestrated cross-context workflows."""

from dataclasses import dataclass
from typing import Optional

from .accounting_services import AccountingService
from .inference_services import DiscoveryService
from .security_services import SecurityService


class OrchestrationError(Exception):
    """Base class for orchestration errors."""

    pass


class InsufficientCreditsError(OrchestrationError):
    """Raised when a user has insufficient credits for a request."""

    pass


class NoNodesAvailableError(OrchestrationError):
    """Raised when no suitable nodes are found for a request."""

    pass


@dataclass
class AuthorizationResult:
    target_ip: str
    token: str
    estimated_cost: int
    encryption_public_key: Optional[str] = None


class OrchestrationService:
    """Orchestrates complex use cases that span multiple bounded contexts."""

    def __init__(
        self,
        accounting_service: AccountingService,
        discovery_service: DiscoveryService,
        security_service: SecurityService,
    ):
        self.accounting_service = accounting_service
        self.discovery_service = discovery_service
        self.security_service = security_service

    def authorize_inference(
        self, requester_pk: str, model_name: str
    ) -> AuthorizationResult:
        """
        Orchestrate the authorization of an inference request.
        1. Ensure user has sufficient credits.
        2. Find an available node for the requested model.
        3. Issue a signed ticket for the requester to present to the node.
        """
        # 1. Accounting: Ensure user has balance
        user = self.accounting_service.create_user_if_not_exists(requester_pk)
        # Simplified for MVP: Minimum 5 minutes of credits (300 seconds)
        if user.balance.seconds < 300:
            raise InsufficientCreditsError("Insufficient credits")

        # 2. Inference: Discovery an idle node
        selected_node = self.discovery_service.select_node_for_model(model_name)
        if not selected_node:
            raise NoNodesAvailableError(f"No idle nodes found for model: {model_name}")

        # 3. Security: Issue a signed ticket
        ticket = self.security_service.issue_authorization_ticket(
            requester_pk, selected_node.node_id
        )

        return AuthorizationResult(
            target_ip=selected_node.tailscale_ip,
            token=ticket.token,
            estimated_cost=300,
            encryption_public_key=selected_node.encryption_public_key,
        )

    def complete_job(
        self,
        job_id: str,
        requester_pk: str,
        worker_node_id: str,
        worker_owner_pk: str,
        duration_seconds: int,
        multiplier: float,
        success: bool,
    ) -> dict:
        """Orchestrate job completion across accounting and reputation."""
        result = {"status": "failed"}

        if success:
            result = self.accounting_service.process_job_completion(
                job_id,
                requester_pk,
                worker_node_id,
                worker_owner_pk,
                duration_seconds,
                multiplier,
            )

        self.discovery_service.record_job_outcome(worker_node_id, success)
        self.discovery_service.recalculate_reputation(worker_node_id)

        return result
