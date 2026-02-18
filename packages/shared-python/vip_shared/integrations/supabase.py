from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import httpx


logger = logging.getLogger("vip-parse.supabase")


class SupabaseMarketingClient:
    """Minimal Supabase client for storing marketing signups via the REST endpoint."""

    def __init__(self) -> None:
        self.url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
        self.service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or ""
        self.table = os.getenv("SUPABASE_EMAIL_TABLE", "email_signups")
        self.enabled = bool(self.url and self.service_key)

    def save_signup(
        self,
        *,
        email: str,
        name: Optional[str] = None,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.enabled:
            logger.info("Supabase disabled; skipping signup capture for %s", email)
            return {"stored": False, "reason": "disabled"}

        payload = {
            "email": email.lower(),
            "name": name,
            "source": source or "landing-page",
            "metadata": metadata or {},
        }
        try:
            with httpx.Client(timeout=20) as client:
                resp = client.post(
                    f"{self.url}/rest/v1/{self.table}",
                    params={"return": "representation"},
                    headers={
                        "apikey": self.service_key,
                        "Authorization": f"Bearer {self.service_key}",
                        "Content-Type": "application/json",
                        "Prefer": "resolution=merge-duplicates",
                    },
                    json=[payload],
                )
                resp.raise_for_status()
                logger.info("Supabase signup stored for %s", email)
                return {"stored": True}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Supabase signup failed for %s: %s", email, exc)
            return {"stored": False, "reason": str(exc)}


__all__ = ["SupabaseMarketingClient"]

