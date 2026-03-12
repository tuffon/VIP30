import os
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

from pwdlib import PasswordHash
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from vip_shared.db.models import OTPCode
from vip_shared.integrations.sendgrid_client import SendGridClient


OTP_EXPIRE_MINUTES = int(os.environ.get("OTP_EXPIRE_MINUTES", "10"))
OTP_MAX_REQUESTS_PER_HOUR = 5
OTP_MAX_ATTEMPTS_PER_CODE = 5

hasher = PasswordHash.recommended()
logger = logging.getLogger("vip-parse.otp")


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

        if resend_api_key and resend_from_email:
            return OTPService._send_via_resend(email, code, resend_api_key, resend_from_email)

        sendgrid_client = SendGridClient()
        if sendgrid_client.enabled:
            return OTPService._send_via_sendgrid(sendgrid_client, email, code)

        if allow_console_fallback:
            print(f"[DEV] OTP for {email}: {code}")
            return True

        logger.error(
            "Failed to send OTP email: no provider configured; expected RESEND_* or SENDGRID_* env vars"
        )
        return False

    @staticmethod
    def _send_via_resend(email: str, code: str, api_key: str, from_email: str) -> bool:
        import resend

        resend.api_key = api_key
        try:
            resend.Emails.send(
                {
                    "from": from_email,
                    "to": email,
                    "subject": "Your verification code",
                    "html": OTPService._render_otp_html(code),
                }
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Resend OTP email failed: %s", exc)
            return False

    @staticmethod
    def _send_via_sendgrid(client: SendGridClient, email: str, code: str) -> bool:
        if not client.enabled:
            return False

        subject = "Your verification code"
        html = OTPService._render_otp_html(code)
        text = (
            "Your verification code\n\n"
            f"{code}\n\n"
            f"This code expires in {OTP_EXPIRE_MINUTES} minutes.\n"
            "If you didn't request this code, you can safely ignore this email."
        )

        try:
            import json
            import httpx

            data = {
                "personalizations": [
                    {
                        "to": [{"email": email}],
                        "subject": subject,
                    }
                ],
                "from": {"email": client.from_email, "name": client.from_name},
                "reply_to": {"email": client.from_email, "name": client.from_name},
                "content": [
                    {"type": "text/plain", "value": text},
                    {"type": "text/html", "value": html},
                ],
            }

            with httpx.Client(timeout=30) as http_client:
                response = http_client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": f"Bearer {client.api_key}",
                        "Content-Type": "application/json",
                    },
                    content=json.dumps(data),
                )
                response.raise_for_status()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("SendGrid OTP email failed: %s", exc)
            return False

    @staticmethod
    def _render_otp_html(code: str) -> str:
        return (
            "<h2>Your verification code</h2>"
            f"<p style='font-size: 32px; font-weight: bold; letter-spacing: 8px;'>{code}</p>"
            f"<p>This code expires in {OTP_EXPIRE_MINUTES} minutes.</p>"
            "<p>If you didn't request this code, you can safely ignore this email.</p>"
        )

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
