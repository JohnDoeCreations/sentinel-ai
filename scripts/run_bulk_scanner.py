"""Run one scheduled Sentinel AI stock-universe scan batch."""

import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.bulk_scanner import scan_next_batch
from utils.scanner_engine import analyze_stock


def main():
    batch_size = int(os.getenv("SENTINEL_BULK_BATCH_SIZE", "25"))
    result = scan_next_batch(analyze_stock, batch_size=batch_size)
    state = result["state"]
    print(
        f"Scanned {len(result['batch'])} symbols. "
        f"Saved results: {len(state['results'])}. "
        f"Errors: {len(state['errors'])}."
    )


if __name__ == "__main__":
    main()
