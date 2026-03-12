from __future__ import annotations

import os

from sqlmodel import Session, select

from vip_shared.db.models import CreditConsumption, CreditGrant, User


def apply_startup_credit_grant(sync_engine) -> None:
    """Apply an optional one-time startup credit grant from environment variables.

    Env vars:
    - STARTUP_CREDIT_EMAIL
    - STARTUP_CREDIT_AMOUNT
    - STARTUP_CREDIT_SOURCE (optional, defaults to a stable deterministic value)
    - STARTUP_CREDIT_NOTES (optional)
    """
    email = os.getenv("STARTUP_CREDIT_EMAIL", "").strip().lower()
    amount_raw = os.getenv("STARTUP_CREDIT_AMOUNT", "").strip()
    notes = os.getenv("STARTUP_CREDIT_NOTES", "").strip() or None

    if not email and not amount_raw:
        return

    if not email or not amount_raw:
        print("startup_credit: skipped because both STARTUP_CREDIT_EMAIL and STARTUP_CREDIT_AMOUNT are required")
        return

    try:
        amount = int(amount_raw)
    except ValueError:
        print(f"startup_credit: skipped because STARTUP_CREDIT_AMOUNT is invalid: {amount_raw!r}")
        return

    if amount <= 0:
        print(f"startup_credit: skipped because STARTUP_CREDIT_AMOUNT must be > 0, got {amount}")
        return

    source = (
        os.getenv("STARTUP_CREDIT_SOURCE", "").strip()
        or f"startup_credit_{email}_{amount}"
    )

    with Session(sync_engine) as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if not user:
            print(f"startup_credit: skipped because user not found: {email}")
            return

        existing = session.exec(
            select(CreditGrant).where(
                CreditGrant.workspace_id == user.workspace_id,
                CreditGrant.source == source,
            )
        ).first()
        if existing:
            print(
                "startup_credit: no-op because grant already exists "
                f"(email={email}, amount={existing.amount}, source={source})"
            )
            return

        grant = CreditGrant(
            workspace_id=user.workspace_id,
            amount=amount,
            source=source,
            granted_by=user.id,
            notes=notes or f"Startup one-time grant ({amount})",
        )
        session.add(grant)
        session.commit()

        total_grants = session.exec(
            select(CreditGrant).where(CreditGrant.workspace_id == user.workspace_id)
        ).all()
        total_consumptions = session.exec(
            select(CreditConsumption).where(CreditConsumption.workspace_id == user.workspace_id)
        ).all()
        balance = sum(item.amount for item in total_grants) - sum(item.amount for item in total_consumptions)

        print(
            "startup_credit: granted "
            f"{amount} credits to {email} "
            f"(source={source}, workspace={user.workspace_id}, balance={balance})"
        )
