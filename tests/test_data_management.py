from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from utils.data_management import (
    DataRestoreError,
    build_export_bundle,
    ensure_daily_backup,
    restore_bundle,
)


def write_sample_data(folder, symbol="AAPL"):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "watchlist.json").write_text(
        json.dumps([symbol]), encoding="utf-8"
    )
    (folder / "alerts.json").write_text(
        json.dumps({"alerts": [], "history": []}), encoding="utf-8"
    )
    (folder / "paper_portfolio.json").write_text(
        json.dumps(
            {
                "starting_cash": 10_000.0,
                "cash": 10_000.0,
                "positions": {},
                "transactions": [],
                "equity_history": [],
            }
        ),
        encoding="utf-8",
    )


class DataManagementTests(unittest.TestCase):
    def test_export_and_restore_round_trip_with_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data"
            backups = root / "backups"
            write_sample_data(data, "AAPL")
            bundle = build_export_bundle(data)

            write_sample_data(data, "MSFT")
            recovery = restore_bundle(bundle, data, backups)

            restored = json.loads(
                (data / "watchlist.json").read_text(encoding="utf-8")
            )
            self.assertEqual(restored, ["AAPL"])
            self.assertTrue(recovery.exists())

    def test_daily_backup_is_created_only_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data"
            backups = root / "backups"
            write_sample_data(data)
            now = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)

            first, first_created = ensure_daily_backup(data, backups, now)
            second, second_created = ensure_daily_backup(data, backups, now)

            self.assertTrue(first_created)
            self.assertFalse(second_created)
            self.assertEqual(first, second)

    def test_restore_rejects_unexpected_archive_paths(self):
        archive_bytes = BytesIO()
        with zipfile.ZipFile(archive_bytes, "w") as archive:
            archive.writestr("../outside.json", "{}")

        with self.assertRaisesRegex(DataRestoreError, "unexpected"):
            restore_bundle(archive_bytes.getvalue())

    def test_restore_rejects_invalid_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "data"
            write_sample_data(data)
            bundle = BytesIO(build_export_bundle(data))
            rewritten = BytesIO()
            with zipfile.ZipFile(bundle, "r") as source, zipfile.ZipFile(
                rewritten, "w"
            ) as target:
                for name in source.namelist():
                    content = source.read(name)
                    if name == "watchlist.json":
                        content = b"{}"
                    target.writestr(name, content)

            with self.assertRaisesRegex(DataRestoreError, "wrong data type"):
                restore_bundle(rewritten.getvalue(), data)


if __name__ == "__main__":
    unittest.main()
