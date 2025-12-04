from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from src.integrations.supabase import SupabaseMarketingClient


router = APIRouter(prefix="/marketing", tags=["marketing"])
logger = logging.getLogger("vip-parse.marketing")
supabase_client = SupabaseMarketingClient()


class MarketingSignupRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    source: Optional[str] = None
    company: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@router.post("/signup")
def create_signup(payload: MarketingSignupRequest) -> Dict[str, Any]:
    """Capture marketing interest and persist to Supabase (if configured)."""
    metadata = payload.metadata or {}
    if payload.company:
        metadata.setdefault("company", payload.company)

    result = supabase_client.save_signup(
        email=payload.email,
        name=payload.name,
        source=payload.source,
        metadata=metadata,
    )
    status = "stored" if result.get("stored") else "queued"
    logger.info("Marketing signup captured (%s): %s", status, payload.email)
    return {"email": payload.email, "status": status, **result}

