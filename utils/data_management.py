"""Local backup, export, and restore tools for personal Sentinel AI data."""

from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
import zipfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_FOLDER = PROJECT_ROOT / "data"
BACKUP_FOLDER = PROJECT_ROOT / "backups"
MAX_RESTORE_BYTES = 10 * 1024 * 1024
MANAGED_FILES = {
    "watchlist.json": list,
    "alerts.json": dict,
    "paper_portfolio.json": dict,
}


class DataRestoreError(ValueError):
    """Raised when an uploaded backup is unsafe or incompatible."""


def _validate_payload(filename, payload):
    """Validate the minimum schema required by the current app."""
    expected_type = MANAGED_FILES[filename]
    if not isinstance(payload, expected_type):
        raise DataRestoreError(f"{filename} has the wrong data type.")

    if filename == "alerts.json":
        if not isinstance(payload.get("alerts"), list) or not isinstance(
            payload.get("history"), list
        ):
            raise DataRestoreError("alerts.json is missing alerts or history lists.")
    elif filename == "paper_portfolio.json":
        required = {"starting_cash", "cash", "positions", "transactions"}
        if not required.issubset(payload):
            raise DataRestoreError("paper_portfolio.json is missing required fields.")
        if not isinstance(payload["positions"], dict) or not isinstance(
            payload["transactions"], list
        ):
            raise DataRestoreError("paper_portfolio.json has invalid collections.")
    return payload


def _read_current_data(data_folder=None):
    """Read and validate every current managed data file."""
    folder = Path(data_folder) if data_folder else DATA_FOLDER
    data = {}
    for filename in MANAGED_FILES:
        path = folder / filename
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise DataRestoreError(f"{filename} is not readable JSON.") from error
        data[filename] = _validate_payload(filename, payload)
    return data


def build_export_bundle(data_folder=None):
    """Return a ZIP export containing validated app data and a manifest."""
    current_data = _read_current_data(data_folder)
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifest = {
        "format": "sentinel-ai-backup",
        "version": 1,
        "created_at": created_at,
        "files": sorted(current_data),
    }

    bundle = BytesIO()
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        for filename, payload in current_data.items():
            archive.writestr(filename, json.dumps(payload, indent=2))
    return bundle.getvalue()


def create_backup(label="manual", data_folder=None, backup_folder=None, now=None):
    """Write a timestamped backup and return its path."""
    folder = Path(backup_folder) if backup_folder else BACKUP_FOLDER
    moment = now or datetime.now(timezone.utc)
    safe_label = "".join(
        character for character in str(label).lower() if character.isalnum() or character == "-"
    ) or "backup"
    filename = f"{moment.strftime('%Y%m%d-%H%M%S')}-{safe_label}.zip"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / filename
    path.write_bytes(build_export_bundle(data_folder))
    return path


def ensure_daily_backup(data_folder=None, backup_folder=None, now=None):
    """Create at most one automatic backup per UTC day."""
    folder = Path(backup_folder) if backup_folder else BACKUP_FOLDER
    moment = now or datetime.now(timezone.utc)
    daily_pattern = f"{moment.strftime('%Y%m%d')}-*-daily.zip"
    if folder.exists():
        existing = sorted(folder.glob(daily_pattern))
        if existing:
            return existing[-1], False
    return create_backup(
        "daily",
        data_folder=data_folder,
        backup_folder=folder,
        now=moment,
    ), True


def list_backups(backup_folder=None):
    """Return backup metadata, newest first."""
    folder = Path(backup_folder) if backup_folder else BACKUP_FOLDER
    if not folder.exists():
        return []
    return [
        {
            "name": path.name,
            "size": path.stat().st_size,
            "modified": datetime.fromtimestamp(
                path.stat().st_mtime, tz=timezone.utc
            ).isoformat(timespec="seconds"),
        }
        for path in sorted(folder.glob("*.zip"), reverse=True)
    ]


def _validate_restore_bundle(bundle_bytes):
    """Return validated JSON payloads from a safe Sentinel backup."""
    if not bundle_bytes:
        raise DataRestoreError("The uploaded backup is empty.")
    if len(bundle_bytes) > MAX_RESTORE_BYTES:
        raise DataRestoreError("The uploaded backup exceeds the 10 MB safety limit.")

    try:
        with zipfile.ZipFile(BytesIO(bundle_bytes), "r") as archive:
            names = set(archive.namelist())
            allowed = set(MANAGED_FILES) | {"manifest.json"}
            if any(name not in allowed for name in names):
                raise DataRestoreError("The backup contains unexpected files or folders.")
            if not set(MANAGED_FILES).issubset(names):
                raise DataRestoreError("The backup does not contain all Sentinel data files.")

            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            if manifest.get("format") != "sentinel-ai-backup":
                raise DataRestoreError("This is not a Sentinel AI backup.")

            payloads = {}
            for filename in MANAGED_FILES:
                payload = json.loads(archive.read(filename).decode("utf-8"))
                payloads[filename] = _validate_payload(filename, payload)
            return payloads
    except DataRestoreError:
        raise
    except (zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DataRestoreError("The uploaded backup is damaged or invalid.") from error


def restore_bundle(bundle_bytes, data_folder=None, backup_folder=None):
    """Validate and restore data atomically after creating a recovery backup."""
    payloads = _validate_restore_bundle(bundle_bytes)
    folder = Path(data_folder) if data_folder else DATA_FOLDER
    recovery = create_backup(
        "pre-restore",
        data_folder=folder,
        backup_folder=backup_folder,
    )
    folder.mkdir(parents=True, exist_ok=True)

    for filename, payload in payloads.items():
        destination = folder / filename
        temporary = destination.with_suffix(".restore.tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(destination)
    return recovery
