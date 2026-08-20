from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from utils.kalshi_collector_status import (
    collector_health,
    load_collector_status,
    save_collector_status,
)


class KalshiCollectorStatusTests(unittest.TestCase):
    def test_save_load_and_health(self):
        now = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "status.json"
            with patch("utils.kalshi_collector_status.COLLECTOR_STATUS_FILE", path):
                save_collector_status(
                    {"markets": 3, "recorded": 2, "settled": 1, "errors": []},
                    finished_at=now,
                )
                status = load_collector_status()
        self.assertEqual(status["markets"], 3)
        self.assertEqual(
            collector_health(status, now=now + timedelta(minutes=5))["label"],
            "Healthy",
        )
        self.assertEqual(
            collector_health(status, now=now + timedelta(minutes=13))["label"],
            "Stale",
        )

    def test_warnings_are_visible(self):
        status = {
            "last_run": "2026-08-20T12:00:00+00:00",
            "errors": ["temporary provider warning"],
        }
        health = collector_health(
            status,
            now=datetime(2026, 8, 20, 12, 5, tzinfo=timezone.utc),
        )
        self.assertEqual(health["label"], "Running with warnings")


if __name__ == "__main__":
    unittest.main()
