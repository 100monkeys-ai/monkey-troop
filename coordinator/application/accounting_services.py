"""Application layer use cases (services) for the Accounting context."""

from datetime import datetime, timezone

from domain.accounting.models import CreditAmount, JobCompletionParams, Transaction, TransactionType, User

from .accounting_ports import TransactionRepository, UserRepository


class AccountingService:
    """Orchestrates accounting use cases."""

    def __init__(self, user_repo: UserRepository, txn_repo: TransactionRepository):
        self.user_repo = user_repo
        self.txn_repo = txn_repo

    def create_user_if_not_exists(self, public_key: str, starter_credits: int = 3600) -> User:
        """Use Case: Provision a new user with initial credits."""
        user = self.user_repo.get_by_public_key(public_key)

        if not user:
            user = User.create_new(public_key, starter_credits)
            self.user_repo.save(user)

            # Record starter grant
            txn = Transaction(
                id=None,
                job_id="starter_grant",
                from_user=None,
                to_user=public_key,
                amount=CreditAmount(starter_credits),
                timestamp=datetime.now(timezone.utc),
                type=TransactionType.STARTER_GRANT,
            )
            self.txn_repo.record_transaction(txn)

        return user

    def reserve_credits(self, public_key: str, amount_seconds: int) -> bool:
        """Use Case: Deduct credits temporarily for an upcoming job."""
        user = self.user_repo.get_by_public_key(public_key)
        if not user:
            return False

        try:
            user.reserve_credits(CreditAmount(amount_seconds))
            self.user_repo.save(user)
            return True
        except ValueError:
            return False

    def process_job_completion(self, params: JobCompletionParams) -> dict:
        """Use Case: Transfer credits from requester to worker after a job."""

        # In a real DDD app, we would use a Unit of Work or Transactional context here
        requester = self.user_repo.get_by_public_key(params.requester_pk)
        worker_owner = self.user_repo.get_by_public_key(params.worker_owner_pk)

        if not requester:
            return {"status": "error", "message": "Requester not found"}

        if not worker_owner:
            worker_owner = self.create_user_if_not_exists(params.worker_owner_pk, 0)

        # Calculate final amount (credits = duration * hardware multiplier)
        credits_to_transfer = int(params.duration_seconds * params.multiplier)
        transfer_amount = CreditAmount(credits_to_transfer)

        # Add to worker
        worker_owner.add_credits(transfer_amount)

        # Save updates
        self.user_repo.save(worker_owner)

        # Record transaction
        txn = Transaction(
            id=None,
            job_id=params.job_id,
            from_user=params.requester_pk,
            to_user=params.worker_owner_pk,
            amount=transfer_amount,
            timestamp=datetime.now(timezone.utc),
            type=TransactionType.JOB_COMPLETION,
        )
        self.txn_repo.record_transaction(txn)

        return {
            "status": "success",
            "credits_transferred": credits_to_transfer,
            "requester_balance": requester.balance.seconds,
            "worker_balance": worker_owner.balance.seconds,
        }
