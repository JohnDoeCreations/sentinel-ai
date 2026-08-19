"""Personal data backup and recovery controls for Sentinel AI."""

from datetime import datetime, timezone
from pathlib import Path
import sys

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.data_management import (
    DataRestoreError,
    build_export_bundle,
    create_backup,
    ensure_daily_backup,
    list_backups,
    restore_bundle,
)


st.set_page_config(
    page_title="Sentinel AI data management",
    page_icon=":material/database:",
    layout="wide",
)

st.title(":material/database: Data management")
st.caption("Protect and move your local watchlist, alerts, and paper-trading data.")
st.info(
    "Backups never include `.streamlit/secrets.toml` or your Massive API key."
)

daily_backup, created = ensure_daily_backup()
backups = list_backups()

with st.container(horizontal=True):
    st.metric("Saved backups", len(backups), border=True)
    st.metric("Latest daily backup", daily_backup.name, border=True)
    st.metric(
        "Backup status",
        "Created now" if created else "Current",
        border=True,
    )

action_columns = st.columns(2)
with action_columns[0]:
    with st.container(border=True):
        st.subheader("Create and export")
        st.write(
            "Download a portable copy or create an extra recovery point before making major changes."
        )
        export_bytes = build_export_bundle()
        export_name = (
            "sentinel-ai-export-"
            + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            + ".zip"
        )
        st.download_button(
            "Download data export",
            data=export_bytes,
            file_name=export_name,
            mime="application/zip",
            icon=":material/download:",
            width="stretch",
        )
        if st.button(
            "Create manual backup",
            icon=":material/backup:",
            width="stretch",
        ):
            path = create_backup("manual")
            st.success(f"Created {path.name}.")
            st.rerun()

with action_columns[1]:
    with st.container(border=True):
        st.subheader("Restore an export")
        st.warning(
            "Restoring replaces your current watchlist, alerts, and paper portfolio. "
            "A recovery backup is created first."
        )
        uploaded_backup = st.file_uploader(
            "Sentinel AI export (.zip)",
            type=["zip"],
        )
        confirm_restore = st.checkbox(
            "I understand that this will replace my current local data.",
            disabled=uploaded_backup is None,
        )
        if st.button(
            "Restore uploaded data",
            icon=":material/restore:",
            type="primary",
            disabled=uploaded_backup is None or not confirm_restore,
            width="stretch",
        ):
            try:
                recovery = restore_bundle(uploaded_backup.getvalue())
                st.success(
                    f"Restore complete. Recovery copy: {recovery.name}."
                )
                st.session_state.clear()
            except DataRestoreError as error:
                st.error(str(error))
            except OSError as error:
                st.error(f"The restore could not be written: {error}")

st.subheader("Local backup history")
backups = list_backups()
if backups:
    table = pd.DataFrame(backups).rename(
        columns={"name": "Backup", "size": "Size", "modified": "Modified (UTC)"}
    )
    st.dataframe(
        table,
        column_config={
            "Size": st.column_config.NumberColumn(format="%d bytes"),
        },
        hide_index=True,
    )
else:
    st.info("No local backups are available yet.")

st.caption(f"Backup folder: {PROJECT_ROOT / 'backups'}")
