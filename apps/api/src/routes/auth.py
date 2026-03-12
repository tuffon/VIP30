from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr
from sqlmodel.ext.asyncio.session import AsyncSession
from src.api.logging_config import get_logger

from vip_shared.db.models import User, Workspace
from src.dependencies.auth import get_current_user
from src.dependencies.database import get_db
from vip_shared.services.auth import AuthService
from vip_shared.services.credits import CreditService
from vip_shared.services.otp import OTPService


auth_router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger("vip-parse.auth")


class OTPSendRequest(BaseModel):
    email: EmailStr


class OTPSendResponse(BaseModel):
    success: bool
    message: str


class OTPVerifyRequest(BaseModel):
    email: EmailStr
    code: str


class UserResponse(BaseModel):
    id: str
    email: str
    role: str


class WorkspaceResponse(BaseModel):
    id: str
    name: str


class OTPVerifyResponse(BaseModel):
    success: bool
    error: str | None = None
    user: UserResponse | None = None
    workspace: WorkspaceResponse | None = None
    is_new_user: bool = False
    credit_balance: int | None = None


@auth_router.post("/otp/send", response_model=OTPSendResponse)
async def send_otp(request: OTPSendRequest, db: AsyncSession = Depends(get_db)):
    allowed, error = await OTPService.check_rate_limit(db, request.email)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": error,
                "message": "Too many OTP requests. Please try again later.",
            },
        )

    logger.info("otp_send_requested", extra={"email": request.email})
    code = await OTPService.create_code(db, request.email)
    sent = await OTPService.send_otp_email(request.email, code)
    if not sent:
        logger.error("otp_send_failed", extra={"email": request.email})
        raise HTTPException(
            status_code=500,
            detail={"error": "email_failed", "message": "Failed to send verification email"},
        )

    logger.info("otp_send_succeeded", extra={"email": request.email})
    return OTPSendResponse(success=True, message="Verification code sent to your email")


@auth_router.post("/otp/verify", response_model=OTPVerifyResponse)
async def verify_otp(
    request: OTPVerifyRequest,
    response: Response,
    client_request: Request,
    db: AsyncSession = Depends(get_db),
):
    success, error_code, _otp_record = await OTPService.verify_code(db, request.email, request.code)
    if not success:
        error_messages = {
            "invalid": "Invalid verification code",
            "expired": "Verification code has expired. Please request a new one.",
            "too_many_attempts": "Too many verification attempts. Please request a new code.",
            "already_used": "This code has already been used",
        }
        raise HTTPException(
            status_code=400,
            detail={
                "error": error_code,
                "message": error_messages.get(error_code, "Verification failed"),
            },
        )

    client_ip = client_request.client.host if client_request.client else None
    user, workspace, is_new_user = await AuthService.get_or_create_user(db, request.email, client_ip)

    if is_new_user:
        await CreditService.grant_signup_bonus(db, workspace.id)

    credit_balance = await CreditService.get_balance(db, workspace.id)

    access_token = AuthService.create_access_token(user.id, workspace.id)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="none",  # Required for cross-site requests (frontend/backend on different subdomains)
        max_age=60 * 60 * 24 * 7,
    )

    return OTPVerifyResponse(
        success=True,
        user=UserResponse(id=str(user.id), email=user.email, role=user.role or "member"),
        workspace=WorkspaceResponse(id=str(workspace.id), name=workspace.name),
        is_new_user=is_new_user,
        credit_balance=credit_balance,
    )


@auth_router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=True,
        samesite="none",
    )
    return {"success": True, "message": "Logged out successfully"}


@auth_router.get("/me", response_model=OTPVerifyResponse)
async def get_me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    workspace = await db.get(Workspace, user.workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=500,
            detail={"error": "workspace_not_found", "message": "Workspace record not found"},
        )
    credit_balance = await CreditService.get_balance(db, workspace.id)
    return OTPVerifyResponse(
        success=True,
        user=UserResponse(id=str(user.id), email=user.email, role=user.role or "member"),
        workspace=WorkspaceResponse(id=str(workspace.id), name=workspace.name),
        is_new_user=False,
        credit_balance=credit_balance,
    )
