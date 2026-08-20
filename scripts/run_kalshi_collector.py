"""Run the Kalshi paper-forecast collector once or continuously."""

import argparse
import os
from pathlib import Path
import sys
import time
import tomllib


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.kalshi_collector import collect_forecast_cycle
from utils.kalshi_collector_status import save_collector_status


def load_api_key():
    """Load Massive credentials from the environment or ignored local secrets."""
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if api_key:
        return api_key
    secrets_path = PROJECT_ROOT / ".streamlit" / "secrets.toml"
    if secrets_path.exists():
        with secrets_path.open("rb") as handle:
            return str(tomllib.load(handle).get("MASSIVE_API_KEY", "")).strip()
    return ""


def main():
    parser = argparse.ArgumentParser(description="Collect Kalshi paper forecasts.")
    parser.add_argument("--watch", action="store_true", help="Run continuously.")
    parser.add_argument("--interval", type=int, default=60, help="Seconds between cycles.")
    args = parser.parse_args()
    api_key = load_api_key()
    if not api_key:
        raise SystemExit("MASSIVE_API_KEY is required in the environment or Streamlit secrets.")
    while True:
        report = collect_forecast_cycle(api_key)
        save_collector_status(report)
        print(
            f"markets={report['markets']} recorded={report['recorded']} "
            f"settled={report['settled']} skipped={report['skipped']} "
            f"errors={len(report['errors'])}",
            flush=True,
        )
        for error in report["errors"]:
            print(f"warning: {error}", flush=True)
        if not args.watch:
            break
        time.sleep(max(15, args.interval))


if __name__ == "__main__":
    main()
