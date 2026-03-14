"""FastAPI endpoints for the Accounting context."""

from fastapi import APIRouter, Depends

from application.accounting_services import AccountingService
from infrastructure.dependencies import get_accounting_service

from .schemas import BalanceResponseSchema

router = APIRouter(prefix="/users", tags=["Accounting"])


@router.get("/{public_key}/balance", response_model=BalanceResponseSchema)
async def get_balance(
    public_key: str, accounting_service: AccountingService = Depends(get_accounting_service)
):
    """Get user's credit balance."""
    user = accounting_service.create_user_if_not_exists(public_key)
    balance = user.balance.seconds
    return {
        "public_key": public_key,
        "balance_seconds": balance,
        "balance_hours": round(balance / 3600, 2),
    }


@router.get("/{public_key}/transactions")
async def get_transactions(
    public_key: str,
    limit: int = 50,
    accounting_service: AccountingService = Depends(get_accounting_service),
):
    """Get transaction history for a user."""
    history = accounting_service.txn_repo.get_history_by_user(public_key, limit)

    return {
        "transactions": [
            {
                "id": txn.id,
                "requester": txn.from_user,
                "worker": txn.to_user,
                "credits": txn.amount.seconds,
                "timestamp": txn.timestamp.isoformat(),
                "type": txn.type,
            }
            for txn in history
        ]
    }
