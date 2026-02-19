from __future__ import annotations

import argparse
import asyncio

from sqlmodel import select

from vip_shared.db import async_session_maker
from vip_shared.db.models import User


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote a user to admin by email")
    parser.add_argument(
        "--email",
        default="benavides.tuffon@gmail.com",
        help="Target user email (default: benavides.tuffon@gmail.com)",
    )
    parser.add_argument(
        "--role",
        default="admin",
        choices=["admin", "member"],
        help="Role to set (default: admin)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print what would change",
    )
    return parser.parse_args()


async def main() -> int:
    args = parse_args()

    async with async_session_maker() as db:
        users_result = await db.exec(select(User).order_by(User.created_at.asc()))
        users = users_result.all()
        print(f"Found {len(users)} total account(s)")
        for user in users:
            print(f"- {user.email} | role={user.role or 'member'} | workspace={user.workspace_id}")

        target = next((u for u in users if u.email.lower() == args.email.lower()), None)
        if not target:
            print(f"ERROR: user not found: {args.email}")
            return 1

        print(f"Matched user: {target.email} (current role={target.role or 'member'})")
        if args.dry_run:
            print(f"DRY RUN: would set role to {args.role}")
            return 0

        target.role = args.role
        await db.commit()
        await db.refresh(target)
        print(f"Updated role: {target.email} -> {target.role}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
