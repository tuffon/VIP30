import asyncio

from vip_shared.services.otp import OTPService


def test_send_otp_prefers_resend_when_configured(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "resend-key")
    monkeypatch.setenv("RESEND_FROM_EMAIL", "noreply@example.com")
    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    monkeypatch.delenv("SENDGRID_FROM_EMAIL", raising=False)

    called = {}

    def fake_resend(email: str, code: str, api_key: str, from_email: str) -> bool:
        called["provider"] = "resend"
        called["email"] = email
        called["code"] = code
        called["api_key"] = api_key
        called["from_email"] = from_email
        return True

    monkeypatch.setattr(OTPService, "_send_via_resend", staticmethod(fake_resend))

    sent = asyncio.run(OTPService.send_otp_email("user@example.com", "123456"))

    assert sent is True
    assert called == {
        "provider": "resend",
        "email": "user@example.com",
        "code": "123456",
        "api_key": "resend-key",
        "from_email": "noreply@example.com",
    }


def test_send_otp_falls_back_to_sendgrid_when_resend_missing(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("RESEND_FROM_EMAIL", raising=False)
    monkeypatch.setenv("SENDGRID_API_KEY", "sg-key")
    monkeypatch.setenv("SENDGRID_FROM_EMAIL", "noreply@example.com")

    called = {}

    def fake_sendgrid(client, email: str, code: str) -> bool:
        called["provider"] = "sendgrid"
        called["email"] = email
        called["code"] = code
        called["enabled"] = client.enabled
        called["from_email"] = client.from_email
        return True

    monkeypatch.setattr(OTPService, "_send_via_sendgrid", staticmethod(fake_sendgrid))

    sent = asyncio.run(OTPService.send_otp_email("user@example.com", "123456"))

    assert sent is True
    assert called == {
        "provider": "sendgrid",
        "email": "user@example.com",
        "code": "123456",
        "enabled": True,
        "from_email": "noreply@example.com",
    }


def test_send_otp_returns_false_when_no_provider_configured(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("RESEND_FROM_EMAIL", raising=False)
    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    monkeypatch.delenv("SENDGRID_FROM_EMAIL", raising=False)
    monkeypatch.setenv("OTP_DEV_CONSOLE_FALLBACK", "false")

    sent = asyncio.run(OTPService.send_otp_email("user@example.com", "123456"))

    assert sent is False
