"""Large-universe management and ranked bulk-scan results."""

from pathlib import Path
import sys

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.bulk_scanner import load_bulk_scan_state, scan_next_batch
from utils.scanner_engine import analyze_stock
from utils.stock_universe import (
    fetch_sp500_symbols,
    load_universe,
    parse_universe_csv,
    parse_universe_text,
    save_universe,
)


st.set_page_config(
    page_title="Sentinel AI stock universe",
    page_icon=":material/public:",
    layout="wide",
)

st.title(":material/public: Stock universe")
st.caption(
    "Manage hundreds of stocks and review saved scanner rankings without "
    "waiting for the entire universe to refresh in the browser."
)

universe = load_universe()
scan_state = load_bulk_scan_state()

with st.container(horizontal=True):
    st.metric("Universe", universe["name"], border=True)
    st.metric("Saved symbols", len(universe["symbols"]), border=True)
    st.metric("Analyzed symbols", len(scan_state["results"]), border=True)
    st.metric("Scan errors", len(scan_state["errors"]), border=True)
    st.metric("Last background scan", scan_state["last_run_at"] or "Never", border=True)

st.subheader("Build the universe")
method = st.segmented_control(
    "Import method",
    ["S&P 500 preset", "Paste symbols", "Upload CSV"],
    default="S&P 500 preset",
)

if method == "S&P 500 preset":
    st.info(
        "Loads the maintained open S&P 500 constituent list. Share-class dots "
        "are converted to Yahoo-compatible dashes."
    )
    if st.button(
        "Load current S&P 500",
        icon=":material/download:",
        type="primary",
    ):
        try:
            with st.spinner("Loading the current constituent list..."):
                symbols, invalid = fetch_sp500_symbols()
                saved, _ = save_universe(symbols, "S&P 500")
            st.success(f'Saved {len(saved["symbols"])} symbols.')
            if invalid:
                st.warning(f"Skipped {len(invalid)} invalid symbol(s).")
            st.rerun()
        except Exception as error:
            st.error(f"Could not load the S&P 500 preset: {error}")
elif method == "Paste symbols":
    with st.form("paste_universe_form"):
        universe_name = st.text_input("Universe name", value="Custom universe")
        pasted = st.text_area(
            "Symbols",
            placeholder="AAPL, MSFT, NVDA\nAMZN\nGOOGL",
            height=180,
        )
        paste_submitted = st.form_submit_button(
            "Save pasted universe",
            icon=":material/save:",
            type="primary",
        )
    if paste_submitted:
        symbols, invalid = parse_universe_text(pasted)
        try:
            saved, _ = save_universe(symbols, universe_name)
            st.success(f'Saved {len(saved["symbols"])} symbols.')
            if invalid:
                st.warning("Skipped: " + ", ".join(invalid[:20]))
            st.rerun()
        except ValueError as error:
            st.error(str(error))
else:
    upload = st.file_uploader("Upload CSV", type=["csv"])
    st.caption("Use a Symbol or Ticker column. Otherwise, the first column is used.")
    if upload is not None:
        upload_name = st.text_input("Universe name", value=Path(upload.name).stem)
        if st.button("Save uploaded universe", icon=":material/save:", type="primary"):
            try:
                symbols, invalid = parse_universe_csv(upload.getvalue())
                saved, _ = save_universe(symbols, upload_name)
                st.success(f'Saved {len(saved["symbols"])} symbols.')
                if invalid:
                    st.warning(f"Skipped {len(invalid)} invalid symbol(s).")
                st.rerun()
            except (UnicodeDecodeError, ValueError) as error:
                st.error(f"Could not import that CSV: {error}")

if not universe["symbols"]:
    st.info("Choose an import method to create your first large stock universe.")
    st.stop()

with st.container(border=True):
    st.subheader("Universe preview")
    search = st.text_input("Find a symbol", placeholder="Example: NVDA")
    visible_symbols = [
        symbol for symbol in universe["symbols"] if search.upper() in symbol
    ]
    st.dataframe(
        pd.DataFrame({"Symbol": visible_symbols}),
        hide_index=True,
        height=260,
    )

st.subheader("Scanner results")
st.caption(
    "The background job scans 25 symbols every 30 minutes during U.S. market "
    "hours and gradually refreshes the entire universe."
)
if st.button(
    "Scan next 25 now",
    icon=":material/play_arrow:",
    help="This may take several minutes. The page shows progress when complete.",
):
    with st.status("Scanning the next batch...", expanded=True) as status:
        try:
            outcome = scan_next_batch(analyze_stock, batch_size=25)
            status.write("Batch: " + ", ".join(outcome["batch"]))
            status.update(label="Batch scan complete", state="complete")
            st.rerun()
        except Exception as error:
            status.update(label=f"Batch scan failed: {error}", state="error")

scan_state = load_bulk_scan_state()
universe_symbol_set = set(universe["symbols"])
results = [
    result
    for symbol, result in scan_state["results"].items()
    if symbol in universe_symbol_set
]
if not results:
    st.info("Saved rankings will appear after the first background or manual batch.")
    st.stop()

results_table = pd.DataFrame(results)
filter_row = st.container(horizontal=True)
minimum_score = filter_row.slider("Minimum score", 0, 4, 0)
signal_options = sorted(results_table["Signal"].dropna().unique().tolist())
signals = filter_row.multiselect("Signals", signal_options)
query = filter_row.text_input("Filter symbol")

filtered = results_table[results_table["Score"] >= minimum_score].copy()
if signals:
    filtered = filtered[filtered["Signal"].isin(signals)]
if query:
    filtered = filtered[
        filtered["Symbol"].str.contains(query.strip().upper(), regex=False)
    ]
filtered = filtered.sort_values(
    ["Score", "Daily Change (%)"], ascending=[False, False]
)

with st.container(horizontal=True):
    st.metric("Matching stocks", len(filtered), border=True)
    st.metric(
        "Bullish watches",
        int((filtered["Signal"] == "BULLISH WATCH").sum()),
        border=True,
    )
    st.metric(
        "Oversold watches",
        int((filtered["Signal"] == "OVERSOLD WATCH").sum()),
        border=True,
    )

display_columns = [
    "Symbol",
    "Price",
    "Daily Change (%)",
    "Score",
    "Rating",
    "Signal",
    "RSI",
    "Scanned At",
]
st.dataframe(
    filtered[[column for column in display_columns if column in filtered]],
    hide_index=True,
    column_config={
        "Symbol": st.column_config.TextColumn(pinned=True),
        "Price": st.column_config.NumberColumn(format="$%.2f"),
        "Daily Change (%)": st.column_config.NumberColumn(format="%.2f%%"),
        "Score": st.column_config.ProgressColumn(min_value=0, max_value=4),
        "RSI": st.column_config.NumberColumn(format="%.2f"),
        "Scanned At": st.column_config.DatetimeColumn(format="MMM DD, YYYY h:mm a"),
    },
)

st.download_button(
    "Download filtered results",
    filtered.to_csv(index=False).encode("utf-8"),
    file_name="sentinel_bulk_scan_results.csv",
    mime="text/csv",
    icon=":material/download:",
)
