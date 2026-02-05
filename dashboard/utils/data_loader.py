"""
Data loader: CSV or SQLite → pandas DataFrame.
Normalizes column names (timestamp_local/timestamp_utc, etc.) for dashboard use.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

# Project root (parent of dashboard/)
ROOT = Path(__file__).resolve().parent.parent.parent


def _load_config() -> dict[str, Any]:
    cfg_path = Path(__file__).resolve().parent.parent / "config.yaml"
    if not cfg_path.is_file():
        return {}
    try:
        import yaml
        with open(cfg_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        return {}


def load_data(config: dict[str, Any] | None = None) -> pd.DataFrame:
    """
    Load surveillance data from CSV, SQLite, or Vigil API per config.
    Returns DataFrame with normalized timestamp columns for dashboards.
    """
    cfg = config or _load_config()
    data_cfg = cfg.get("data", {})
    source = (data_cfg.get("source") or "csv").strip().lower()

    if source == "api":
        base = (data_cfg.get("api_base_url") or "http://localhost:5000").rstrip("/")
        limit = data_cfg.get("api_get_data_limit", 5000)
        try:
            import urllib.request
            url = f"{base}/get_data?limit={limit}"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                import json
                data = json.loads(resp.read().decode())
            if not data:
                return pd.DataFrame()
            df = pd.DataFrame(data)
        except Exception:
            return pd.DataFrame()
    elif source == "sqlite":
        path = data_cfg.get("sqlite_path", "surveillance.db")
        table = data_cfg.get("sqlite_table", "ai_data")
        full_path = ROOT / path if not Path(path).is_absolute() else Path(path)
        if not full_path.is_file():
            return pd.DataFrame()
        try:
            df = pd.read_sql_query(f"SELECT * FROM {table}", f"sqlite:///{full_path}")
        except Exception:
            return pd.DataFrame()
    else:
        path = data_cfg.get("csv_path", "surveillance_log_clean.csv")
        full_path = ROOT / path if not Path(path).is_absolute() else Path(path)
        if not full_path.is_file():
            return pd.DataFrame()
        try:
            df = pd.read_csv(full_path)
        except Exception:
            return pd.DataFrame()

    if df.empty:
        return df

    # API/get_data: build timestamp_local from date + time if needed
    if "timestamp_local" not in df.columns and "date" in df.columns and "time" in df.columns:
        try:
            df["timestamp_local"] = pd.to_datetime(df["date"].astype(str) + " " + df["time"].astype(str), errors="coerce")
        except Exception:
            pass
    if "event" not in df.columns and "event_type" in df.columns:
        df["event"] = df["event_type"]

    # Normalize time columns for dashboard
    for col in ["local_timestamp", "timestamp_utc", "timestamp_local", "date", "time"]:
        if col in df.columns and df[col].notna().any():
            if col in ("local_timestamp", "timestamp_utc", "timestamp_local"):
                df[col] = pd.to_datetime(df[col], errors="coerce")
    if "timestamp_local" not in df.columns and "local_timestamp" in df.columns:
        df["timestamp_local"] = df["local_timestamp"]

    # Ensure numeric (including parser output: value, time_since_prev)
    for col in ("crowd_count", "threat_score", "anomaly_score", "estimated_height_cm", "value", "time_since_prev"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def apply_filters(
    df: pd.DataFrame,
    date_from: str | None = None,
    date_to: str | None = None,
    scene: str | None = None,
    object_type: str | None = None,
    event_type: str | None = None,
    threat_min: float | None = None,
    anomaly_min: float | None = None,
    clothing_search: str | None = None,
    value_min: float | None = None,
) -> pd.DataFrame:
    """Apply global filters; returns filtered DataFrame."""
    if df.empty:
        return df
    out = df.copy()
    ts_col = "timestamp_local" if "timestamp_local" in out.columns else "local_timestamp"
    if ts_col not in out.columns:
        ts_col = "timestamp_utc"
    if ts_col in out.columns and out[ts_col].notna().any():
        out[ts_col] = pd.to_datetime(out[ts_col], errors="coerce")
        if date_from:
            out = out[out[ts_col].dt.date >= pd.to_datetime(date_from).date()]
        if date_to:
            out = out[out[ts_col].dt.date <= pd.to_datetime(date_to).date()]
    if scene and "scene" in out.columns:
        out = out[out["scene"].astype(str).str.lower() == scene.lower()]
    if object_type and "object" in out.columns:
        out = out[out["object"].astype(str).str.lower() == object_type.lower()]
    if event_type and "event" in out.columns:
        out = out[out["event"].astype(str).str.lower().str.contains(event_type.lower(), na=False)]
    if threat_min is not None and "threat_score" in out.columns:
        out = out[pd.to_numeric(out["threat_score"], errors="coerce").fillna(0) >= threat_min]
    if anomaly_min is not None and "anomaly_score" in out.columns:
        out = out[pd.to_numeric(out["anomaly_score"], errors="coerce").fillna(0) >= anomaly_min]
    if clothing_search and "clothing_description" in out.columns:
        out = out[out["clothing_description"].astype(str).str.lower().str.contains(clothing_search.lower(), na=False)]
    if value_min is not None:
        for col in ("value", "estimated_height_cm"):
            if col in out.columns:
                out = out[pd.to_numeric(out[col], errors="coerce").fillna(0) >= float(value_min)]
                break
    return out


def get_api_base(config: dict[str, Any] | None = None) -> str | None:
    """Return API base URL when data source is api, else None."""
    cfg = config or _load_config()
    data_cfg = cfg.get("data", {})
    if (data_cfg.get("source") or "").strip().lower() != "api":
        return None
    return (data_cfg.get("api_base_url") or "http://localhost:5000").rstrip("/")


def get_vigil_ui_base(config: dict[str, Any] | None = None) -> str | None:
    """Return Vigil UI base URL for 'Play at moment' links (opens React app with ?playback_ts=)."""
    cfg = config or _load_config()
    data_cfg = cfg.get("data", {})
    url = (data_cfg.get("vigil_ui_url") or data_cfg.get("api_base_url") or "http://localhost:5000").strip().rstrip("/")
    return url if url else None


def fetch_system_status(config: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Fetch Vigil system status from /api/v1/system_status. Returns None if not using API or on error."""
    base = get_api_base(config)
    if not base:
        return None
    try:
        import urllib.request
        req = urllib.request.Request(f"{base}/api/v1/system_status", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            import json
            return json.loads(resp.read().decode())
    except Exception:
        return None


def fetch_streams(config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Fetch Vigil streams from /streams for Live page. Returns [] if not using API or on error."""
    base = get_api_base(config)
    if not base:
        return []
    try:
        import urllib.request
        req = urllib.request.Request(f"{base}/streams", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            import json
            data = json.loads(resp.read().decode())
            return data if isinstance(data, list) else []
    except Exception:
        return []


def fetch_sites(config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Fetch sites from Vigil /sites for Map page."""
    base = get_api_base(config)
    if not base:
        return []
    try:
        import urllib.request
        req = urllib.request.Request(f"{base}/sites", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            import json
            data = json.loads(resp.read().decode())
            return data if isinstance(data, list) else []
    except Exception:
        return []


def fetch_camera_positions(config: dict[str, Any] | None = None, site_id: str | None = None) -> list[dict[str, Any]]:
    """Fetch camera positions from Vigil /camera_positions for Map page."""
    base = get_api_base(config)
    if not base:
        return []
    try:
        import urllib.request
        url = f"{base}/camera_positions" + (f"?site_id={site_id}" if site_id else "")
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            import json
            data = json.loads(resp.read().decode())
            return data if isinstance(data, list) else []
    except Exception:
        return []


def search_query_parser(query: str) -> dict[str, Any]:
    """
    Simple natural-language-ish parser for search bar.
    e.g. "loitering at night gray clothing" → event=loitering, nighttime=True, clothing=gray
    """
    q = (query or "").lower().strip()
    out = {}
    if "loitering" in q or "loiter" in q:
        out["event_type"] = "loitering"
    if "motion" in q:
        out["event_type"] = "motion"
    if "night" in q or "nighttime" in q:
        out["night_only"] = True
    for color in ("gray", "grey", "black", "white", "dark", "red", "blue", "brown"):
        if color in q:
            out["clothing_search"] = color
            break
    if "indoor" in q:
        out["scene"] = "Indoor"
    if "outdoor" in q:
        out["scene"] = "Outdoor"
    return out
