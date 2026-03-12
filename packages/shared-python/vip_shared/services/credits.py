import os
import uuid

from sqlalchemy.exc import IntegrityError
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from vip_shared.db.models import CreditConsumption, CreditGrant


DEFAULT_CREDITS_SIGNUP = int(os.environ.get("DEFAULT_CREDITS_SIGNUP", "50"))


class CreditAlreadyConsumedError(Exception):
    pass


class CreditService:
    @staticmethod
    async def grant_signup_bonus(db: AsyncSession, workspace_id: uuid.UUID) -> CreditGrant:
        grant = CreditGrant(
            workspace_id=workspace_id,
            amount=DEFAULT_CREDITS_SIGNUP,
            source="signup_bonus",
            granted_by=None,
            notes="Trial credits for new signup",
        )
        db.add(grant)
        await db.commit()
        await db.refresh(grant)
        return grant

    @staticmethod
    async def grant_manual(
        db: AsyncSession,
        workspace_id: uuid.UUID,
        amount: int,
        *,
        source: str = "manual_test_grant",
        notes: str | None = None,
        granted_by: uuid.UUID | None = None,
    ) -> CreditGrant:
        grant = CreditGrant(
            workspace_id=workspace_id,
            amount=amount,
            source=source,
            granted_by=granted_by,
            notes=notes,
        )
        db.add(grant)
        await db.commit()
        await db.refresh(grant)
        return grant

    async def get_balance(db: AsyncSession, workspace_id: uuid.UUID) -> int:
        grants_stmt = select(func.coalesce(func.sum(CreditGrant.amount), 0)).where(
            CreditGrant.workspace_id == workspace_id
        )
        grants_result = await db.exec(grants_stmt)
        total_grants = grants_result.one()

        consumptions_stmt = select(func.coalesce(func.sum(CreditConsumption.amount), 0)).where(
            CreditConsumption.workspace_id == workspace_id
        )
        consumptions_result = await db.exec(consumptions_stmt)
        total_consumptions = consumptions_result.one()

        return int(total_grants) - int(total_consumptions)

    @staticmethod
    async def consume_credit(
        db: AsyncSession,
        workspace_id: uuid.UUID,
        job_id: uuid.UUID,
        amount: int = 1,
    ) -> CreditConsumption:
        consumption = CreditConsumption(
            workspace_id=workspace_id,
            job_id=job_id,
            amount=amount,
        )
        db.add(consumption)
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise CreditAlreadyConsumedError("credit_already_consumed") from exc

        await db.refresh(consumption)
        return consumption

    @staticmethod
    async def has_consumed_credit(db: AsyncSession, job_id: uuid.UUID) -> bool:
        stmt = select(CreditConsumption.id).where(CreditConsumption.job_id == job_id)
        result = await db.exec(stmt)
        return result.first() is not None
