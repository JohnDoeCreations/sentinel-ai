"""Local heartbeat state for the automatic Kalshi paper collector."""

from datetime import datetime, timezone
import json
from pathlib import Path


COLLECTOR_STATUS_FILE = (
    Path(__file__).resolve().parents[1] / "data" / "kalshi_collector_status.json"
)


def save_collector_status(report, finished_at=None):
    """Atomically persist a sanitized collector-cycle heartbeat."""
    finished_at = finished_at or datetime.now(timezone.utc)
    status = {
        "last_run": finished_at.isoformat(timespec="seconds"),
        "markets": int(report.get("markets", 0)),
        "recorded": int(report.get("recorded", 0)),
        "settled": int(report.get("settled", 0)),
        "skipped": int(report.get("skipped", 0)),
        "errors": [str(error) for error in report.get("errors", [])][:20],
    }
    COLLECTOR_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = COLLECTOR_STATUS_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(status, indent=2), encoding="utf-8")
    temporary.replace(COLLECTOR_STATUS_FILE)
    return status


def load_collector_status():
    """Return the latest valid heartbeat or None."""
    if not COLLECTOR_STATUS_FILE.exists():
        return None
    try:
        status = json.loads(COLLECTOR_STATUS_FILE.read_text(encoding="utf-8"))
        datetime.fromisoformat(str(status["last_run"]).replace("Z", "+00:00"))
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None
    return status


def collector_health(status=None, now=None, stale_after_minutes=12):
    """Classify the heartbeat as healthy, warning, stale, or not started."""
    status = status if status is not None else load_collector_status()
    if not status:
        return {"label": "Not started", "color": "gray", "age_minutes": None}
    now = now or datetime.now(timezone.utc)
    last_run = datetime.fromisoformat(str(status["last_run"]).replace("Z", "+00:00"))
    age_minutes = max(0.0, (now - last_run).total_seconds() / 60)
    if age_minutes > stale_after_minutes:
        label, color = "Stale", "red"
    elif status.get("errors"):
        label, color = "Running with warnings", "orange"
    else:
        label, color = "Healthy", "green"
    return {"label": label, "color": color, "age_minutes": age_minutes}
