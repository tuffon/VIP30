import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from src.api.main import app


client = TestClient(app)


def test_marketing_signup_requires_valid_email() -> None:
    resp = client.post("/marketing/signup", json={"email": "bad"})
    assert resp.status_code == 422


def test_marketing_signup_returns_status_when_disabled(monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    resp = client.post(
        "/marketing/signup",
        json={"email": "sample@example.com", "name": "Taylor"},
    )
    data = resp.json()
    assert resp.status_code == 200
    assert data["email"] == "sample@example.com"
    assert data["status"] == "queued"
    assert data["stored"] is False

