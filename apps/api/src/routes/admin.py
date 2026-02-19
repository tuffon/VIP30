from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.dependencies.auth import require_admin
from src.dependencies.database import get_db
from vip_shared.db.models import CreditConsumption, CreditGrant, User, Workspace
from vip_shared.services.credits import CreditService


admin_router = APIRouter(prefix="/admin", tags=["admin"])


class AdminUserItem(BaseModel):
    id: str
    email: str
    role: str
    workspace_id: str
    workspace_name: Optional[str] = None
    created_at: datetime
    balance: int


class AdminUsersResponse(BaseModel):
    items: List[AdminUserItem]
    total_count: int
    page: int
    per_page: int


class AdminGrantCreditsRequest(BaseModel):
    amount: int
    notes: Optional[str] = None


class AdminGrantCreditsResponse(BaseModel):
    success: bool
    user_id: str
    workspace_id: str
    granted_amount: int
    balance: int


class AdminSetRoleByEmailRequest(BaseModel):
    email: EmailStr
    role: str = "admin"


class AdminSetRoleResponse(BaseModel):
    success: bool
    user_id: str
    email: str
    role: str


@admin_router.get("/users", response_model=AdminUsersResponse)
async def list_users(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100),
    search: Optional[str] = Query(default=None),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    where_clause = True
    if search:
        term = f"%{search.lower()}%"
        where_clause = func.lower(User.email).like(term)

    total_stmt = select(func.count()).select_from(User).where(where_clause)
    total_result = await db.exec(total_stmt)
    total_count = int(total_result.one())

    users_stmt = (
        select(User, Workspace)
        .join(Workspace, Workspace.id == User.workspace_id)
        .where(where_clause)
        .order_by(User.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    users_result = await db.exec(users_stmt)
    rows = users_result.all()

    if not rows:
        return AdminUsersResponse(items=[], total_count=total_count, page=page, per_page=per_page)

    workspace_ids = [user.workspace_id for user, _workspace in rows]

    grants_stmt = (
        select(CreditGrant.workspace_id, func.coalesce(func.sum(CreditGrant.amount), 0))
        .where(CreditGrant.workspace_id.in_(workspace_ids))
        .group_by(CreditGrant.workspace_id)
    )
    grants_result = await db.exec(grants_stmt)
    grants_map = {workspace_id: int(total) for workspace_id, total in grants_result.all()}

    consumptions_stmt = (
        select(CreditConsumption.workspace_id, func.coalesce(func.sum(CreditConsumption.amount), 0))
        .where(CreditConsumption.workspace_id.in_(workspace_ids))
        .group_by(CreditConsumption.workspace_id)
    )
    consumptions_result = await db.exec(consumptions_stmt)
    consumptions_map = {workspace_id: int(total) for workspace_id, total in consumptions_result.all()}

    items: List[AdminUserItem] = []
    for user, workspace in rows:
        grants = grants_map.get(user.workspace_id, 0)
        consumptions = consumptions_map.get(user.workspace_id, 0)
        items.append(
            AdminUserItem(
                id=str(user.id),
                email=user.email,
                role=user.role or "member",
                workspace_id=str(user.workspace_id),
                workspace_name=workspace.name,
                created_at=user.created_at,
                balance=grants - consumptions,
            )
        )

    return AdminUsersResponse(items=items, total_count=total_count, page=page, per_page=per_page)


@admin_router.post(
    "/users/{user_id}/credits/grant",
    response_model=AdminGrantCreditsResponse,
    status_code=status.HTTP_200_OK,
)
async def grant_credits_to_user(
    user_id: uuid.UUID,
    payload: AdminGrantCreditsRequest,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be greater than 0")
    if payload.amount > 10000:
        raise HTTPException(status_code=400, detail="amount too large")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    await CreditService.grant_manual(
        db,
        workspace_id=user.workspace_id,
        amount=payload.amount,
        source="admin_portal_grant",
        notes=payload.notes or f"Granted by admin {admin_user.email}",
        granted_by=admin_user.id,
    )

    balance = await CreditService.get_balance(db, user.workspace_id)

    return AdminGrantCreditsResponse(
        success=True,
        user_id=str(user.id),
        workspace_id=str(user.workspace_id),
        granted_amount=payload.amount,
        balance=balance,
    )


@admin_router.post("/users/role", response_model=AdminSetRoleResponse, status_code=status.HTTP_200_OK)
async def set_role_by_email(
    payload: AdminSetRoleByEmailRequest,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    target = await db.exec(select(User).where(func.lower(User.email) == payload.email.lower()))
    user = target.first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    role = (payload.role or "member").strip().lower()
    if role not in {"member", "admin"}:
        raise HTTPException(status_code=400, detail="invalid role")

    user.role = role
    await db.commit()
    await db.refresh(user)

    return AdminSetRoleResponse(success=True, user_id=str(user.id), email=user.email, role=user.role)
