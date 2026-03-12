import uuid

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from src.api.main import app
from src.dependencies.database import get_db
from src.routes import auth as auth_route
from vip_shared.db.models import User, Workspace
from vip_shared.services.auth import AuthService
from vip_shared.services.credits import CreditService
from vip_shared.services.otp import OTPService


class DummyDB:
    async def close(self):
        return None


def _make_user(email: str, workspace_id: uuid.UUID | None = None) -> User:
    return User(
        id=uuid.uuid4(),
        workspace_id=workspace_id or uuid.uuid4(),
        email=email,
        role="member",
    )


def _make_workspace(workspace_id: uuid.UUID) -> Workspace:
    return Workspace(id=workspace_id, name="Test Workspace")


def test_verify_otp_adds_bonus_for_vipclaimservice_login(monkeypatch):
    user = _make_user("ingrid@vipclaimservice.com")
    workspace = _make_workspace(user.workspace_id)
    manual_calls: list[dict] = []

    async def db_override():
        yield DummyDB()

    async def verify_code(_db, _email, _code):
        return True, "", object()

    async def get_or_create_user(_db, _email, _ip):
        return user, workspace, False

    async def grant_manual(_db, workspace_id, amount, *, source, notes=None, granted_by=None):
        manual_calls.append(
            {
                "workspace_id": workspace_id,
                "amount": amount,
                "source": source,
                "notes": notes,
                "granted_by": granted_by,
            }
        )
        return object()

    async def get_balance(_db, _workspace_id):
        return 42

    monkeypatch.setattr(OTPService, "verify_code", staticmethod(verify_code))
    monkeypatch.setattr(AuthService, "get_or_create_user", staticmethod(get_or_create_user))
    monkeypatch.setattr(CreditService, "grant_manual", staticmethod(grant_manual))
    monkeypatch.setattr(CreditService, "get_balance", staticmethod(get_balance))

    app.dependency_overrides[get_db] = db_override
    with TestClient(app) as client:
        resp = client.post("/auth/otp/verify", json={"email": user.email, "code": "123456"})

    assert resp.status_code == 200
    assert resp.json()["credit_balance"] == 42
    assert len(manual_calls) == 1
    assert manual_calls[0]["amount"] == auth_route.VIPCLAIMS_LOGIN_BONUS_AMOUNT
    assert manual_calls[0]["source"] == "vipclaimservice_login_bonus"
    assert manual_calls[0]["granted_by"] == user.id
    app.dependency_overrides = {}


def test_verify_otp_does_not_add_bonus_for_other_domains(monkeypatch):
    user = _make_user("user@example.com")
    workspace = _make_workspace(user.workspace_id)
    manual_calls = 0

    async def db_override():
        yield DummyDB()

    async def verify_code(_db, _email, _code):
        return True, "", object()

    async def get_or_create_user(_db, _email, _ip):
        return user, workspace, False

    async def grant_manual(*args, **kwargs):
        nonlocal manual_calls
        manual_calls += 1
        return object()

    async def get_balance(_db, _workspace_id):
        return 7

    monkeypatch.setattr(OTPService, "verify_code", staticmethod(verify_code))
    monkeypatch.setattr(AuthService, "get_or_create_user", staticmethod(get_or_create_user))
    monkeypatch.setattr(CreditService, "grant_manual", staticmethod(grant_manual))
    monkeypatch.setattr(CreditService, "get_balance", staticmethod(get_balance))

    app.dependency_overrides[get_db] = db_override
    with TestClient(app) as client:
        resp = client.post("/auth/otp/verify", json={"email": user.email, "code": "123456"})

    assert resp.status_code == 200
    assert resp.json()["credit_balance"] == 7
    assert manual_calls == 0
    app.dependency_overrides = {}
