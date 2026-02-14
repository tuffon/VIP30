# Plan 02-01 Summary: OTP Send/Verify Endpoints with Rate Limiting

## Status

Completed on 2026-02-14.

## Scope Executed

- Added/confirmed auth dependencies in `apps/vip-parse/requirements.txt` and `apps/vip-parse/requirements-web.txt`:
  - `pwdlib[argon2]>=0.3.0`
  - `pyjwt>=2.11.0`
  - `resend>=2.21.0`
- Implemented OTP service in `apps/vip-parse/src/services/otp.py`:
  - 6-digit code generation
  - 10-minute expiry
  - previous-code invalidation on re-issue
  - request rate limiting (5/hour/email)
  - attempt limiting (5/code)
  - Resend integration with dev logging fallback
- Implemented OTP endpoints in `apps/vip-parse/src/routes/auth.py`:
  - `POST /auth/otp/send`
  - `POST /auth/otp/verify`
  - specific auth error messaging
- Registered auth routes in `apps/vip-parse/src/api/main.py`.

## Requirement Mapping

- AUTH-01: Implemented (`/auth/otp/send`, 6-digit OTP generation)
- AUTH-02: Implemented (`OTP_EXPIRE_MINUTES`, expiry check)
- AUTH-03: Implemented (invalidates prior unused OTPs on new issue)
- AUTH-04: Implemented (5 OTP requests/hour/email)
- AUTH-05: Implemented (5 verify attempts/code)
- AUTH-06: Implemented (specific invalid/expired/too_many_attempts messages)

## Verification Evidence

- `pip install -r requirements.txt` succeeds in active `/tmp` environment.
- Imports pass:
  - `from src.services.otp import OTPService`
  - `from src.routes.auth import auth_router`
- Endpoint smoke checks via `TestClient` (dependency/method overrides) pass:
  - `POST /auth/otp/send` returns 200 for valid request
  - rate-limited send returns 429 with `too_many_requests`
  - `POST /auth/otp/verify` wrong code returns 400 `invalid`
  - repeated invalid verify path returns 400 `too_many_attempts`

## Notes

- DB-backed integration checks were validated via service/endpoint behavior with controlled overrides and fakes in this session.
