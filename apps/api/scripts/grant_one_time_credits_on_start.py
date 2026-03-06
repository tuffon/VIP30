from __future__ import annotations

import asyncio
import os

from sqlmodel import select

from vip_shared.db import async_session_maker
from vip_shared.db.models import CreditGrant, User
from vip_shared.services.credits import CreditService


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


async def main() -> int:
    email = _env("ONE_TIME_CREDIT_EMAIL").lower()
    amount_raw = _env("ONE_TIME_CREDIT_AMOUNT")
    source = _env("ONE_TIME_CREDIT_SOURCE")

    if not email or not amount_raw or not source:
        print("one_time_credit: skipped (ONE_TIME_CREDIT_EMAIL/AMOUNT/SOURCE not fully set)")
        return 0

    try:
        amount = int(amount_raw)
    except ValueError:
        print("one_time_credit: skipped (ONE_TIME_CREDIT_AMOUNT must be an integer)")
        return 0

    if amount <= 0:
        print("one_time_credit: skipped (ONE_TIME_CREDIT_AMOUNT must be > 0)")
        return 0

    async with async_session_maker() as db:
        user_result = await db.exec(select(User).where(User.email == email))
        user = user_result.first()
        if not user:
            print(f"one_time_credit: skipped (user not found: {email})")
            return 0

        existing_result = await db.exec(
            select(CreditGrant).where(
                CreditGrant.workspace_id == user.workspace_id,
                CreditGrant.source == source,
            )
        )
        existing = existing_result.first()
        if existing:
            balance = await CreditService.get_balance(db, user.workspace_id)
            print(
                "one_time_credit: no-op (already granted) "
                f"grant_id={existing.id} amount={existing.amount} source={existing.source}"
            )
            print(f"one_time_credit: current_balance={balance}")
            return 0

        grant = await CreditService.grant_manual(
            db,
            workspace_id=user.workspace_id,
            amount=amount,
            source=source,
            notes=f"One-time deploy grant ({amount})",
            granted_by=user.id,
        )
        balance = await CreditService.get_balance(db, user.workspace_id)
        print(
            f"one_time_credit: success grant_id={grant.id} "
            f"email={email} amount={grant.amount} source={grant.source}"
        )
        print(f"one_time_credit: updated_balance={balance}")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
