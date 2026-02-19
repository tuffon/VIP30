import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple

import jwt
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from vip_shared.db.models import User, Workspace


JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", str(60 * 24 * 7)))


class AuthService:
    @staticmethod
    def create_access_token(user_id: uuid.UUID, workspace_id: uuid.UUID) -> str:
        expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
        payload = {
            "sub": str(user_id),
            "workspace_id": str(workspace_id),
            "exp": expire,
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> Optional[dict]:
        try:
            return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email)
        result = await db.exec(stmt)
        return result.first()

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
        return await db.get(User, user_id)

    @staticmethod
    async def create_workspace_and_user(
        db: AsyncSession,
        email: str,
        login_ip: Optional[str] = None,
    ) -> Tuple[User, Workspace, bool]:
        workspace = Workspace(name=f"{email.split('@')[0]}'s Workspace")
        db.add(workspace)
        await db.flush()

        user = User(
            email=email,
            workspace_id=workspace.id,
            role="member",
            last_login_at=datetime.utcnow(),
            last_login_ip=login_ip,
            login_method="email_otp",
        )
        db.add(user)
        await db.flush()

        workspace.owner_user_id = user.id

        await db.commit()
        await db.refresh(user)
        await db.refresh(workspace)
        return user, workspace, True

    @staticmethod
    async def get_or_create_user(
        db: AsyncSession,
        email: str,
        login_ip: Optional[str] = None,
    ) -> Tuple[User, Workspace, bool]:
        existing_user = await AuthService.get_user_by_email(db, email)
        if existing_user:
            existing_user.last_login_at = datetime.utcnow()
            existing_user.last_login_ip = login_ip
            existing_user.login_method = "email_otp"
            await db.commit()
            await db.refresh(existing_user)

            workspace = await db.get(Workspace, existing_user.workspace_id)
            return existing_user, workspace, False

        return await AuthService.create_workspace_and_user(db, email, login_ip)
