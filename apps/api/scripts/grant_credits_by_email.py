from __future__ import annotations

import argparse
import asyncio

from sqlmodel import select

from vip_shared.db import async_session_maker
from vip_shared.db.models import CreditGrant, User
from vip_shared.services.credits import CreditService


DEFAULT_EMAIL = "benavides.tuffon@gmail.com"
DEFAULT_AMOUNT = 100000
DEFAULT_SOURCE = "one_time_test_grant_100000_2026_03_06"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Grant one-time credits to a user by email.")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help=f"Target user email (default: {DEFAULT_EMAIL})")
    parser.add_argument("--amount", type=int, default=DEFAULT_AMOUNT, help=f"Grant amount (default: {DEFAULT_AMOUNT})")
    parser.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help=f"Idempotency/source key (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without writing",
    )
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    email = args.email.strip().lower()

    if args.amount <= 0:
        print("ERROR: amount must be > 0")
        return 2

    async with async_session_maker() as db:
        user_result = await db.exec(select(User).where(User.email == email))
        user = user_result.first()
        if not user:
            print(f"ERROR: user not found: {email}")
            return 1

        workspace_id = user.workspace_id

        existing_result = await db.exec(
            select(CreditGrant).where(
                CreditGrant.workspace_id == workspace_id,
                CreditGrant.source == args.source,
            )
        )
        existing = existing_result.first()
        if existing:
            balance = await CreditService.get_balance(db, workspace_id)
            print(
                "NO-OP: grant already exists "
                f"(grant_id={existing.id}, amount={existing.amount}, source={existing.source})"
            )
            print(f"Current balance: {balance}")
            return 0

        if args.dry_run:
            print(
                "DRY RUN: would grant "
                f"{args.amount} credits to {email} (workspace={workspace_id}, source={args.source})"
            )
            return 0

        grant = await CreditService.grant_manual(
            db,
            workspace_id=workspace_id,
            amount=args.amount,
            source=args.source,
            notes=f"One-time test grant ({args.amount})",
            granted_by=user.id,
        )
        balance = await CreditService.get_balance(db, workspace_id)
        print(
            f"SUCCESS: granted {grant.amount} credits to {email} "
            f"(grant_id={grant.id}, source={grant.source})"
        )
        print(f"Updated balance: {balance}")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
