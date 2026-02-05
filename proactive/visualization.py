"""
Visualization & forensic tools: timelines, heatmaps, replay.

- Timeline: detections per hour (person), anomaly spikes.
- Heatmaps: position density if bbox coords available.
- Replay: query DB by date/person → summary or frame export list.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd
    HAS_PLOT = True
except ImportError:
    HAS_PLOT = False
    plt = None
    pd = None


def plot_detections_per_hour(
    df: "pd.DataFrame",
    object_filter: str = "person",
    output_path: str | Path = "detections_per_hour.png",
) -> None:
    """Bar plot: hour of day (x) vs count of detections (y)."""
    if not HAS_PLOT or df is None or df.empty:
        return
    ts_col = "local_timestamp" if "local_timestamp" in df.columns else "timestamp_utc"
    if ts_col not in df.columns:
        return
    obj_col = "object" if "object" in df.columns else None
    if obj_col:
        df = df[df[obj_col].astype(str).str.lower() == object_filter.lower()]
    df = df.copy()
    df["ts"] = pd.to_datetime(df[ts_col], errors="coerce")
    df = df.dropna(subset=["ts"])
    if df.empty:
        return
    df["hour"] = df["ts"].dt.hour
    hourly = df.groupby("hour").size().reindex(range(24), fill_value=0)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(hourly.index, hourly.values, color="steelblue", alpha=0.8)
    ax.set_xlabel("Hour of day")
    ax.set_ylabel(f"Count ({object_filter})")
    ax.set_title(f"Detections per hour ({object_filter})")
    fig.tight_layout()
    fig.savefig(output_path, dpi=100)
    plt.close()


def plot_anomaly_timeline(
    df: "pd.DataFrame",
    threat_col: str = "threat_score",
    anomaly_col: str = "anomaly_score",
    output_path: str | Path = "timeline_anomalies.png",
) -> None:
    """Timeline: x=time, y=threat/anomaly; highlight spikes."""
    if not HAS_PLOT or df is None or df.empty:
        return
    ts_col = "local_timestamp" if "local_timestamp" in df.columns else "timestamp_utc"
    if ts_col not in df.columns:
        return
    df = df.copy()
    df["ts"] = pd.to_datetime(df[ts_col], errors="coerce")
    df = df.dropna(subset=["ts"]).sort_values("ts")
    fig, ax = plt.subplots(figsize=(12, 3))
    x = df["ts"]
    if threat_col in df.columns:
        ax.fill_between(x, 0, df[threat_col].fillna(0), alpha=0.5, label="threat_score")
    if anomaly_col in df.columns:
        ax.fill_between(x, 0, df[anomaly_col].fillna(0) * 100, alpha=0.5, label="anomaly_score x100")
    ax.set_xlabel("Time")
    ax.set_ylabel("Score")
    ax.set_title("Threat & anomaly over time")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(output_path, dpi=100)
    plt.close()


def plot_position_heatmap(
    df: "pd.DataFrame",
    x_col: str = "bbox_x",
    y_col: str = "bbox_y",
    output_path: str | Path = "heatmap_positions.png",
) -> None:
    """2D heatmap of detection positions (if bbox center coords exist)."""
    if not HAS_PLOT or df is None:
        return
    for c in (x_col, y_col):
        if c not in df.columns or df[c].isna().all():
            return
    df = df.dropna(subset=[x_col, y_col])
    if df.empty:
        return
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.hexbin(df[x_col], df[y_col], gridsize=20, cmap="YlOrRd", mincnt=1)
    ax.set_xlabel(x_col)
    ax.set_ylabel(y_col)
    ax.set_title("Detection position density")
    fig.tight_layout()
    fig.savefig(output_path, dpi=100)
    plt.close()


def replay_summary(
    conn: sqlite3.Connection,
    date_from: str | None = None,
    date_to: str | None = None,
    person_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Query detection_events (and optionally tracks) for replay.
    Returns list of event dicts with timestamp_utc, object, event, track_id, etc.
    """
    c = conn.cursor()
    sql = """
        SELECT id, timestamp_utc, local_timestamp, camera_id, object, event, scene,
               threat_score, track_id, person_id
        FROM detection_events
        WHERE 1=1
    """
    params: list[Any] = []
    if date_from:
        sql += " AND date(timestamp_utc) >= date(?)"
        params.append(date_from)
    if date_to:
        sql += " AND date(timestamp_utc) <= date(?)"
        params.append(date_to)
    if person_id is not None:
        sql += " AND person_id = ?"
        params.append(person_id)
    sql += " ORDER BY timestamp_utc"
    c.execute(sql, params)
    cols = [d[0] for d in c.description]
    return [dict(zip(cols, row)) for row in c.fetchall()]


def replay_export_frames_description(events: list[dict[str, Any]]) -> str:
    """Produce a text description of a replay (for montage or frame export list)."""
    lines = [
        f"Replay: {len(events)} events",
        "",
    ]
    for e in events[:50]:
        ts = e.get("timestamp_utc") or e.get("local_timestamp")
        obj = e.get("object", "")
        ev = e.get("event", "")
        track = e.get("track_id")
        line = f"  {ts}  object={obj}  event={ev}  track_id={track}"
        lines.append(line)
    if len(events) > 50:
        lines.append(f"  ... and {len(events) - 50} more")
    return "\n".join(lines)
