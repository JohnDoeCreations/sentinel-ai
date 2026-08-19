"""Optional Supabase-backed JSON persistence with local fallback."""

from copy import deepcopy
from datetime import datetime, timezone
import os

import requests
import streamlit as st


def _setting(name):
    value = os.getenv(name, "").strip()
    if value:
        return value
    try:
        return str(st.secrets.get(name, "")).strip()
    except (FileNotFoundError, RuntimeError):
        return ""


def cloud_storage_enabled():
    """Return whether both Supabase credentials are configured."""
    return bool(_setting("SUPABASE_URL") and _setting("SUPABASE_SERVICE_KEY"))


def _request(method, key, value=None):
    base_url = _setting("SUPABASE_URL").rstrip("/")
    service_key = _setting("SUPABASE_SERVICE_KEY")
    if not base_url or not service_key:
        return None

    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    url = f"{base_url}/rest/v1/app_state"

    if method == "GET":
        response = requests.get(
            url,
            params={"key": f"eq.{key}", "select": "value"},
            headers=headers,
            timeout=15,
        )
    else:
        headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
        response = requests.post(
            url,
            params={"on_conflict": "key"},
            json={
                "key": key,
                "value": value,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            headers=headers,
            timeout=15,
        )

    response.raise_for_status()
    return response


def load_cloud_json(key, default):
    """Load one JSON document, returning a copy of default when unavailable."""
    if not cloud_storage_enabled():
        return None
    try:
        response = _request("GET", key)
        rows = response.json() if response is not None else []
        return rows[0]["value"] if rows else deepcopy(default)
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
        return None


def save_cloud_json(key, value):
    """Upsert one JSON document and report whether cloud storage succeeded."""
    if not cloud_storage_enabled():
        return False
    try:
        _request("POST", key, value)
        return True
    except requests.RequestException:
        return False
