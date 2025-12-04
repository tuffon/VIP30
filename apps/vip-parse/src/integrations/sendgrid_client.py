from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

import httpx


logger = logging.getLogger("vip-parse.sendgrid")


class SendGridClient:
    """Minimal SendGrid helper for transactional + marketing emails."""

    def __init__(self) -> None:
        self.api_key = os.getenv("SENDGRID_API_KEY") or ""
        self.from_email = os.getenv("SENDGRID_FROM_EMAIL") or os.getenv("SENDGRID_SENDER", "")
        self.from_name = os.getenv("SENDGRID_FROM_NAME") or os.getenv("BRAND_NAME", "ScopeVista")
        self.brand_name = os.getenv("BRAND_NAME", "ScopeVista")
        self.marketing_footer = os.getenv(
            "SENDGRID_MARKETING_FOOTER",
            "ScopeVista automates bid comparisons so you can close files faster.",
        )
        self.enabled = bool(self.api_key and self.from_email)

    def send_bidcomp_ready_email(
        self,
        to_email: str,
        download_url: str,
        summary: Optional[str] = None,
    ) -> bool:
        """Send a document-ready email with marketing call-to-action."""
        if not self.enabled:
            logger.info("SendGrid disabled; skipping email to %s", to_email)
            return False

        subject = f"{self.brand_name} bid comparison is ready"
        preheader = summary or "Your file is packaged and ready to download."
        html_content = self._render_html(download_url, summary)

        data: Dict[str, Any] = {
            "personalizations": [
                {
                    "to": [{"email": to_email}],
                    "subject": subject,
                }
            ],
            "from": {"email": self.from_email, "name": self.from_name},
            "reply_to": {"email": self.from_email, "name": self.from_name},
            "content": [
                {"type": "text/plain", "value": self._render_text(download_url, summary)},
                {"type": "text/html", "value": html_content},
            ],
            "headers": {
                "X-ScopeVista-Preheader": preheader,
            },
        }

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    content=json.dumps(data),
                )
                resp.raise_for_status()
            logger.info("SendGrid email queued to %s", to_email)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("SendGrid email failed: %s", exc)
            return False

    def _render_html(self, download_url: str, summary: Optional[str]) -> str:
        headline = summary or "Your latest bid comparison report is packaged and ready."
        return f"""
        <div style="font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color:#0f172a;">
          <h1 style="font-size:22px;">{self.brand_name} report ready</h1>
          <p style="font-size:16px; line-height:1.5; margin-bottom:20px;">{headline}</p>
          <p style="margin-bottom:28px;">Download your XLSX package using the secure link below:</p>
          <p style="margin-bottom:36px;">
            <a href="{download_url}" style="display:inline-flex; padding:12px 24px; background-color:#2563eb; color:#fff; text-decoration:none; border-radius:999px;">
              Download Bid Comp
            </a>
          </p>
          <p style="font-size:15px; line-height:1.6; color:#475569;">
            {self.marketing_footer}
          </p>
          <p style="font-size:13px; color:#94a3b8; margin-top:32px;">
            You’re receiving this notification because you requested an update when the document was ready.
          </p>
        </div>
        """

    def _render_text(self, download_url: str, summary: Optional[str]) -> str:
        headline = summary or "Your latest bid comparison report is ready."
        return (
            f"{headline}\n\n"
            f"Download: {download_url}\n\n"
            f"{self.marketing_footer}\n"
            "You are receiving this because you requested an email when the document finished processing."
        )


__all__ = ["SendGridClient"]

