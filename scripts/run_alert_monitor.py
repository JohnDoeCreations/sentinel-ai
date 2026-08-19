"""Scheduled entry point for Sentinel AI's background alert monitor."""

from datetime import datetime, time
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.alert_monitor import check_enabled_alerts
from utils.cloud_storage import cloud_storage_enabled
from utils.notifications import email_notifications_enabled, send_alert_email
from utils.paper_trading import load_portfolio
from utils.scanner_engine import analyze_stock


EASTERN = ZoneInfo("America/New_York")


def market_is_open(now=None):
    """Return True during normal U.S. weekday market hours."""
    now = now or datetime.now(EASTERN)
    local_now = now.astimezone(EASTERN)
    return (
        local_now.weekday() < 5
        and time(9, 30) <= local_now.time().replace(tzinfo=None) <= time(16, 0)
    )


def main():
    if not cloud_storage_enabled():
        raise RuntimeError("Supabase credentials are required for scheduled alerts.")

    if os.getenv("SENTINEL_SEND_TEST_EMAIL", "").lower() == "true":
        send_alert_email(
            [
                {
                    "symbol": "TEST",
                    "message": "Automatic Sentinel AI email alerts are working.",
                }
            ]
        )
        print("Test notification email sent.")

    force = os.getenv("SENTINEL_FORCE_ALERT_CHECK", "").lower() == "true"
    if not force and not market_is_open():
        print("Market is closed; no alert check was needed.")
        return 0

    portfolio = load_portfolio()
    result = check_enabled_alerts(
        analyze_stock,
        positions=portfolio.get("positions", {}),
    )
    email_sent = False
    if result["newly_triggered"] and email_notifications_enabled():
        send_alert_email(result["newly_triggered"])
        email_sent = True
    print(
        "Alert check complete: "
        f"{result['checked']} checked, "
        f"{len(result['newly_triggered'])} new triggers, "
        f"{len(result['errors'])} errors, "
        f"email {'sent' if email_sent else 'not needed'}."
    )
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
