"""Email notifications for newly triggered Sentinel AI alerts."""

from html import escape
import os

import requests


RESEND_EMAIL_URL = "https://api.resend.com/emails"


def email_notifications_enabled():
    return bool(os.getenv("RESEND_API_KEY") and os.getenv("ALERT_EMAIL"))


def send_alert_email(triggers, *, api_key=None, recipient=None):
    """Send one digest containing only newly triggered alerts."""
    triggers = list(triggers)
    if not triggers:
        return None

    api_key = api_key or os.getenv("RESEND_API_KEY", "").strip()
    recipient = recipient or os.getenv("ALERT_EMAIL", "").strip()
    if not api_key or not recipient:
        raise RuntimeError("Email notification credentials are not configured.")

    rows = "".join(
        "<li><strong>"
        + escape(str(item.get("symbol", "Alert")))
        + ":</strong> "
        + escape(str(item.get("message", "Condition reached.")))
        + "</li>"
        for item in triggers
    )
    response = requests.post(
        RESEND_EMAIL_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "from": "Sentinel AI <onboarding@resend.dev>",
            "to": [recipient],
            "subject": f"Sentinel AI: {len(triggers)} alert(s) triggered",
            "html": (
                "<h2>Sentinel AI alert</h2><ul>"
                + rows
                + "</ul><p>Open Sentinel AI to review the latest market data.</p>"
            ),
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json().get("id")
