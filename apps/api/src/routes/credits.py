from datetime import datetime
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from vip_shared.db.models import CreditConsumption, CreditGrant, User
from src.dependencies.auth import require_auth
from src.dependencies.database import get_db
from vip_shared.services.credits import CreditService


credits_router = APIRouter(prefix="/credits", tags=["credits"])


class CreditTransactionItem(BaseModel):
    id: str
    type: str
    amount: int
    source: Optional[str] = None
    job_id: Optional[str] = None
    created_at: datetime
    notes: Optional[str] = None


class CreditsListResponse(BaseModel):
    items: List[CreditTransactionItem]
    total_count: int
    page: int
    per_page: int


class CreditBalanceResponse(BaseModel):
    balance: int


class TestCreditGrantRequest(BaseModel):
    amount: int
    notes: Optional[str] = None


class TestCreditGrantResponse(BaseModel):
    success: bool
    balance: int
    granted_amount: int


def _test_credit_grants_enabled() -> bool:
    return os.getenv("ENABLE_TEST_CREDIT_GRANTS", "false").strip().lower() in {"1", "true", "yes"}


@credits_router.get("", response_model=CreditsListResponse)
async def list_credit_transactions(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    workspace_id = current_user.workspace_id

    grants_stmt = select(CreditGrant).where(CreditGrant.workspace_id == workspace_id)
    grants_result = await db.exec(grants_stmt)
    grants = grants_result.all()

    consumptions_stmt = select(CreditConsumption).where(CreditConsumption.workspace_id == workspace_id)
    consumptions_result = await db.exec(consumptions_stmt)
    consumptions = consumptions_result.all()

    items: List[CreditTransactionItem] = [
        CreditTransactionItem(
            id=str(grant.id),
            type="grant",
            amount=grant.amount,
            source=grant.source,
            created_at=grant.created_at,
            notes=grant.notes,
        )
        for grant in grants
    ]
    items.extend(
        CreditTransactionItem(
            id=str(consumption.id),
            type="consumption",
            amount=consumption.amount,
            source="job_completion",
            job_id=str(consumption.job_id),
            created_at=consumption.created_at,
        )
        for consumption in consumptions
    )

    items.sort(key=lambda item: item.created_at, reverse=True)

    total_count = len(items)
    offset = (page - 1) * per_page
    paginated_items = items[offset : offset + per_page]

    return CreditsListResponse(
        items=paginated_items,
        total_count=total_count,
        page=page,
        per_page=per_page,
    )


@credits_router.get("/balance", response_model=CreditBalanceResponse)
async def get_credit_balance(
    current_user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    balance = await CreditService.get_balance(db, current_user.workspace_id)
    return CreditBalanceResponse(balance=balance)


@credits_router.post("/testing/grant", response_model=TestCreditGrantResponse, status_code=status.HTTP_200_OK)
async def grant_test_credits(
    payload: TestCreditGrantRequest,
    current_user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    if not _test_credit_grants_enabled():
        raise HTTPException(status_code=404, detail="not found")

    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be greater than 0")
    if payload.amount > 1000:
        raise HTTPException(status_code=400, detail="amount too large")

    await CreditService.grant_manual(
        db,
        workspace_id=current_user.workspace_id,
        amount=payload.amount,
        source="manual_test_grant",
        notes=payload.notes or "manual test grant",
        granted_by=current_user.id,
    )
    balance = await CreditService.get_balance(db, current_user.workspace_id)
    return TestCreditGrantResponse(success=True, balance=balance, granted_amount=payload.amount)
