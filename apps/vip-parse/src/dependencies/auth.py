import uuid
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from vip_shared.db.models import User
from src.dependencies.database import get_db
from vip_shared.services.auth import AuthService


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    token = request.cookies.get("access_token")
    if not token:
        return None

    payload = AuthService.decode_token(token)
    if not payload:
        return None

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        return None

    return await AuthService.get_user_by_id(db, user_id)


async def get_current_user(user: Optional[User] = Depends(get_current_user_optional)) -> User:
    if not user:
        raise HTTPException(
            status_code=401,
            detail={"error": "not_authenticated", "message": "Authentication required"},
        )
    return user


require_auth = get_current_user
