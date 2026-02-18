import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple

from pwdlib import PasswordHash
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from vip_shared.db.models import OTPCode


OTP_EXPIRE_MINUTES = int(os.environ.get("OTP_EXPIRE_MINUTES", "10"))
OTP_MAX_REQUESTS_PER_HOUR = 5
OTP_MAX_ATTEMPTS_PER_CODE = 5

hasher = PasswordHash.recommended()


class OTPService:
    @staticmethod
    def generate_code() -> str:
        return f"{secrets.randbelow(1000000):06d}"

    @staticmethod
    async def check_rate_limit(db: AsyncSession, email: str) -> Tuple[bool, str]:
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        stmt = select(OTPCode).where(OTPCode.email == email, OTPCode.created_at > one_hour_ago)
        result = await db.exec(stmt)
        recent_codes = result.all()

        if len(recent_codes) >= OTP_MAX_REQUESTS_PER_HOUR:
            return False, "too_many_requests"

        return True, ""

    @staticmethod
    async def invalidate_previous_codes(db: AsyncSession, email: str) -> None:
        stmt = select(OTPCode).where(OTPCode.email == email, OTPCode.used_at.is_(None))
        result = await db.exec(stmt)
        now = datetime.utcnow()
        for code in result.all():
            code.used_at = now
        await db.commit()

    @staticmethod
    async def create_code(db: AsyncSession, email: str) -> str:
        await OTPService.invalidate_previous_codes(db, email)

        code = OTPService.generate_code()
        code_hash = hasher.hash(code)
        expires_at = datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES)

        otp = OTPCode(
            email=email,
            code_hash=code_hash,
            expires_at=expires_at,
            attempts=0,
        )
        db.add(otp)
        await db.commit()

        return code

    @staticmethod
    async def send_otp_email(email: str, code: str) -> bool:
        resend_api_key = os.environ.get("RESEND_API_KEY", "").strip()
        resend_from_email = os.environ.get("RESEND_FROM_EMAIL", "").strip()
        allow_console_fallback = os.environ.get("OTP_DEV_CONSOLE_FALLBACK", "false").lower() == "true"

        if not resend_api_key:
            if allow_console_fallback:
                print(f"[DEV] OTP for {email}: {code}")
                return True
            print("Failed to send OTP email: RESEND_API_KEY is not configured")
            return False

        if not resend_from_email:
            print("Failed to send OTP email: RESEND_FROM_EMAIL is not configured")
            return False

        import resend

        resend.api_key = resend_api_key
        try:
            resend.Emails.send(
                {
                    "from": resend_from_email,
                    "to": email,
                    "subject": "Your verification code",
                    "html": (
                        "<h2>Your verification code</h2>"
                        f"<p style='font-size: 32px; font-weight: bold; letter-spacing: 8px;'>{code}</p>"
                        f"<p>This code expires in {OTP_EXPIRE_MINUTES} minutes.</p>"
                        "<p>If you didn't request this code, you can safely ignore this email.</p>"
                    ),
                }
            )
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to send OTP email: {exc}")
            return False

    @staticmethod
    async def verify_code(
        db: AsyncSession,
        email: str,
        code: str,
    ) -> Tuple[bool, str, Optional[OTPCode]]:
        stmt = (
            select(OTPCode)
            .where(OTPCode.email == email, OTPCode.used_at.is_(None))
            .order_by(OTPCode.created_at.desc())
        )
        result = await db.exec(stmt)
        otp = result.first()

        if not otp:
            return False, "invalid", None

        if otp.attempts >= OTP_MAX_ATTEMPTS_PER_CODE:
            return False, "too_many_attempts", None

        otp.attempts += 1
        await db.commit()

        if datetime.utcnow() > otp.expires_at:
            return False, "expired", None

        if not hasher.verify(code, otp.code_hash):
            return False, "invalid", None

        otp.used_at = datetime.utcnow()
        await db.commit()

        return True, "", otp
