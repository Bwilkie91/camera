#!/usr/bin/env python3
"""
Surveillance log parser and analyzer.

Parses semi-structured text dumps from a YOLOv8-based AI surveillance system,
cleans and normalizes data, and produces a pandas DataFrame plus summary
reports and visualizations.

- Uses regex for line splitting; handles variable column counts and missing fields.
- Robust per-line try/except; failed lines yield partial rows with Nones.
- Output: cleaned DataFrame, cleaned_logs.csv, analysis plots, Markdown report.

Usage:
    python scripts/surveillance_log_parser.py
    SURVEILLANCE_LOG_PATH=/path/to/log.txt python scripts/surveillance_log_parser.py
"""

from __future__ import annotations

import os
import re
import warnings
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# Optional: matplotlib/seaborn for plotting (graceful fallback)
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_PLOT = True
except ImportError:
    HAS_PLOT = False

try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False

# -----------------------------------------------------------------------------
# Raw log: paste your full export here, or set SURVEILLANCE_LOG_PATH to a file.
# -----------------------------------------------------------------------------

SAMPLE_RAW_LOG = """date,time,individual,facial_features,object,pose,emotion,scene,event,crowd_count,camera_id,model_version,system_id,integrity_hash,perceived_age_range,hair_color,estimated_height_cm,build,stress_level,threat_score,anomaly_score,clothing_description,timestamp_utc
2/4/26 23:38:27 Unidentified pose=Unknown,emotion=Neutral person Indoor Motion Detected 1 0 yolov8n.pt Mac.attlocal.net 0 30-44 gray 170 medium low 0 0.0 gray top/body 2026-02-05T04:38:27Z a1b2c3d4e5f6789012345678901234567890123456789012345678901234
2/4/26 23:39:01 Unidentified pose=Unknown,emotion=Neutral person Indoor None 1 0 yolov8n.pt Mac.attlocal.net 0 30-44 gray 172 medium low 0 0.0 gray top/body 2026-02-05T04:39:01Z b2c3d4e5f6a789012345678901234567890123456789012345678901234567
2/4/26 23:40:15 Unidentified pose=Standing,emotion=Neutral person Outdoor Loitering Detected 1 0 yolov8n.pt Mac.attlocal.net 0 18-29 brown 178 slim low 25 0.5 dark top 2026-02-05T04:40:15Z c3d4e5f6a7b890123456789012345678901234567890123456789012345678
2/4/26 23:41:00 Unidentified pose=Unknown,emotion=Neutral dog Outdoor Motion Detected 0 0 yolov8n.pt Mac.attlocal.net 2026-02-05T04:41:00Z d4e5f6a7b8c90123456789012345678901234567890123456789012345678901
2/4/26 23:42:00 Unidentified pose=Unknown,emotion=Neutral person Indoor Motion Detected 1 0 yolov8n.pt Mac.attlocal.net 0 30-44 gray 170 medium low 0 0.0 gray top/body 2026-02-05T04:42:00Z e5f6a7b8c9d012345678901234567890123456789012345678901234567890
"""

# Known null-like values
NULL_VALUES = {"none", "unknown", "n/a", "null", ""}
# Regex: local timestamp at start (M/D/YY or MM/DD/YYYY, then time)
RE_LOCAL_TS = re.compile(r"^(\d{1,2}/\d{1,2}/\d{2,4})\s+(\d{1,2}:\d{2}:\d{2})\s*")
# Trailing hex hash (16–64 chars)
RE_TRAILING_HASH = re.compile(r"\s+([a-fA-F0-9]{16,64})\s*$")
# Key=value pairs
RE_KV = re.compile(r"(\w+)=([^,\s]+)")
# Split middle by comma (preserve segments with spaces)
RE_COMMA_SPLIT = re.compile(r",(?=\s*(?:[^\s,]+\s+)*[^\s,]*(?:\s|$))")


def _to_snake(s: str) -> str:
    """Normalize header/field name to snake_case."""
    s = s.strip().replace("-", "_").replace(" ", "_")
    return re.sub(r"_+", "_", s).strip("_").lower()


def _parse_local_timestamp(date_str: str, time_str: str) -> datetime | None:
    """Parse local timestamp (MM/DD/YY or MM/DD/YYYY and HH:MM:SS)."""
    try:
        parts = date_str.split("/")
        year = int(parts[-1])
        if year < 100:
            year += 2000 if year < 50 else 1900
        month = int(parts[0])
        day = int(parts[1])
        h, m, s = map(int, time_str.split(":"))
        return datetime(year, month, day, h, m, s)
    except (ValueError, IndexError, TypeError):
        return None


def _parse_utc_timestamp(s: str) -> datetime | None:
    """Parse UTC ISO-like string to datetime."""
    if not s or (isinstance(s, str) and s.strip().lower() in NULL_VALUES):
        return None
    s = str(s).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _clean_value(raw: Any) -> Any:
    """Strip quotes, normalize None/Unknown/N/A, convert numbers where appropriate."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).strip().strip('"\'')
    if not s or s.lower() in NULL_VALUES:
        return None
    if s.isdigit():
        return int(s)
    try:
        return float(s)
    except ValueError:
        return s


# Canonical columns (order and names we always emit)
CANONICAL_COLUMNS = [
    "local_timestamp", "date", "time", "individual", "facial_features", "object", "pose", "emotion",
    "scene", "event", "crowd_count", "camera_id", "model_version", "system_id", "integrity_hash",
    "perceived_age_range", "hair_color", "estimated_height_cm", "build", "stress_level",
    "threat_score", "anomaly_score", "clothing_description", "timestamp_utc",
]


def _infer_columns_from_header(header_line: str) -> list[str]:
    """Parse header line into normalized column names; fallback to canonical."""
    try:
        # Support comma- or tab-separated header
        parts = re.split(r"[\t,]+", header_line)
        parts = [p.strip() for p in parts if p.strip()]
        if not parts:
            return list(CANONICAL_COLUMNS)
        names = [_to_snake(p) for p in parts]
        if "local_timestamp" not in names:
            names.insert(0, "local_timestamp")
        if "integrity_hash" not in names:
            names.append("integrity_hash")
        return names
    except Exception:
        return list(CANONICAL_COLUMNS)


def _parse_space_segment(segment: str, row: dict[str, Any], expected_columns: list[str]) -> None:
    """Parse a space-separated segment into row fields (object, scene, event, hair_color, value, etc.)."""
    tokens = re.split(r"\s+", segment.strip())
    object_types = {"person", "dog", "cat", "bed", "bottle", "cell", "phone", "none"}
    scenes = {"indoor", "outdoor"}
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        lower = tok.lower()
        if lower == "unidentified" and "individual" in expected_columns:
            row["individual"] = tok
            i += 1
            continue
        if "=" in tok and not tok.startswith("="):
            k, _, v = tok.partition("=")
            k, v = _to_snake(k.strip()), v.strip()
            if k in expected_columns:
                row[k] = _clean_value(v)
            i += 1
            continue
        if lower == "motion" and i + 1 < len(tokens) and tokens[i + 1].lower() == "detected":
            if "event" in expected_columns:
                row["event"] = "Motion Detected"
            i += 2
            continue
        if lower == "loitering" and i + 1 < len(tokens) and tokens[i + 1].lower() == "detected":
            if "event" in expected_columns:
                row["event"] = "Loitering Detected"
            i += 2
            continue
        if lower == "none" and row.get("event") is None and "event" in expected_columns:
            row["event"] = None
            i += 1
            continue
        if lower in object_types:
            if "object" in expected_columns:
                row["object"] = None if lower == "none" else tok
            i += 1
            continue
        if lower in scenes:
            if "scene" in expected_columns:
                row["scene"] = tok
            i += 1
            continue
        if "yolov8" in lower and lower.endswith(".pt"):
            if "model_version" in expected_columns:
                row["model_version"] = tok
            i += 1
            continue
        if ("." in tok or "attlocal" in lower) and re.match(r"^[\w.-]+$", tok):
            if "system_id" in expected_columns and row.get("system_id") is None:
                row["system_id"] = tok
            i += 1
            continue
        if re.match(r"^\d{2}-\d{2}$", tok):
            if "perceived_age_range" in expected_columns:
                row["perceived_age_range"] = tok
            i += 1
            continue
        # 3-digit number after hair_color -> estimated_height_cm / value
        if re.match(r"^\d{3}$", tok):
            if "estimated_height_cm" in expected_columns:
                try:
                    row["estimated_height_cm"] = int(tok)
                except ValueError:
                    pass
            i += 1
            continue
        if lower in ("slim", "medium", "heavy"):
            if "build" in expected_columns:
                row["build"] = tok
            i += 1
            continue
        if lower in ("low", "medium", "high") and "stress_level" in expected_columns:
            row["stress_level"] = tok
            i += 1
            continue
        if re.match(r"^\d+\.\d+$", tok):
            if "anomaly_score" in expected_columns:
                try:
                    row["anomaly_score"] = float(tok)
                except ValueError:
                    pass
            i += 1
            continue
        if tok.isdigit():
            n = int(tok)
            if "crowd_count" in expected_columns and row.get("crowd_count") is None:
                row["crowd_count"] = n
            elif "camera_id" in expected_columns and row.get("camera_id") is None:
                row["camera_id"] = n
            elif "threat_score" in expected_columns:
                if row.get("threat_score") is None or (n > 0 and row.get("threat_score") == 0):
                    row["threat_score"] = n
            i += 1
            continue
        if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", tok):
            if "timestamp_utc" in expected_columns:
                row["timestamp_utc"] = _parse_utc_timestamp(tok)
            i += 1
            continue
        if lower in ("gray", "grey", "brown", "black", "white", "blonde", "dark"):
            if "hair_color" in expected_columns and row.get("hair_color") is None:
                row["hair_color"] = tok
            elif "clothing_description" in expected_columns:
                prev = row.get("clothing_description") or ""
                row["clothing_description"] = (prev + " " + tok).strip() if prev else tok
            i += 1
            continue
        if "/" in tok or "top" in lower or "body" in lower:
            if "clothing_description" in expected_columns:
                prev = row.get("clothing_description") or ""
                row["clothing_description"] = (prev + " " + tok).strip() if prev else tok
            i += 1
            continue
        if "clothing_description" in expected_columns and tok:
            prev = row.get("clothing_description") or ""
            row["clothing_description"] = (prev + " " + tok).strip() if prev else tok
        i += 1


def _parse_data_line(line: str, expected_columns: list[str]) -> dict[str, Any] | None:
    """
    Parse a single data line into a dict. Uses regex for timestamp and hash;
    middle is split by comma then tokenized. Robust: missing fields become None.
    """
    line = line.strip()
    if not line:
        return None

    row: dict[str, Any] = {c: None for c in expected_columns}

    try:
        # 1) Leading local timestamp (regex)
        m = RE_LOCAL_TS.match(line)
        if m:
            date_part, time_part = m.group(1), m.group(2)
            row["local_timestamp"] = _parse_local_timestamp(date_part, time_part)
            line = line[m.end():].strip()
        else:
            row["local_timestamp"] = None

        # 2) Trailing integrity_hash
        hash_m = RE_TRAILING_HASH.search(line)
        if hash_m:
            row["integrity_hash"] = hash_m.group(1)
            line = line[: hash_m.start()].strip()

        # 3) Middle: split by comma (regex to handle variable spacing)
        segments = [s.strip() for s in re.split(r"\s*,\s*", line) if s.strip()]

        object_types = {"person", "dog", "cat", "bed", "bottle", "none"}
        scenes = {"indoor", "outdoor"}

        for seg in segments:
            if not seg:
                continue
            if " " in seg:
                _parse_space_segment(seg, row, expected_columns)
                continue
            kv = RE_KV.search(seg)
            if kv:
                k, v = _to_snake(kv.group(1)), kv.group(2)
                if k in expected_columns:
                    row[k] = _clean_value(v)
                continue
            lower = seg.lower()
            if lower in object_types:
                row["object"] = None if lower == "none" else seg
            elif lower in scenes:
                row["scene"] = seg
            elif seg == "Unidentified":
                row["individual"] = seg
            elif "yolov8" in lower and lower.endswith(".pt"):
                row["model_version"] = seg
            elif seg.isdigit():
                if row.get("crowd_count") is None:
                    row["crowd_count"] = int(seg)
            elif re.match(r"^\d+\.\d+$", seg):
                row["anomaly_score"] = float(seg)
            elif re.match(r"^\d+$", seg) and row.get("threat_score") is None:
                row["threat_score"] = int(seg)
            elif "top" in lower or "body" in lower or "gray" in lower or "dark" in lower:
                row["clothing_description"] = seg
            elif re.match(r"^\d{2}-\d{2}$", seg):
                row["perceived_age_range"] = seg
            elif lower in ("gray", "brown", "black", "white", "blonde"):
                row["hair_color"] = seg
            elif lower in ("slim", "medium", "heavy"):
                row["build"] = seg
            elif lower in ("standing", "unknown"):
                if row.get("pose") is None:
                    row["pose"] = None if lower == "unknown" else seg
            elif lower == "neutral":
                row["emotion"] = seg
            elif re.match(r"^\d{3}$", seg):
                row["estimated_height_cm"] = int(seg)
            elif re.match(r"^\d{4}-\d{2}-\d{2}T", seg):
                row["timestamp_utc"] = _parse_utc_timestamp(seg)
            elif seg and ("." in seg or "attlocal" in seg.lower()) and row.get("system_id") is None:
                row["system_id"] = seg

        for col in ("crowd_count", "threat_score", "estimated_height_cm", "camera_id"):
            if col in row and row[col] is not None and not isinstance(row[col], (int, float)):
                try:
                    row[col] = int(float(row[col]))
                except (ValueError, TypeError):
                    row[col] = None

    except Exception:
        # On any error, return row with whatever we have (partial parse)
        pass

    return row


def parse_surveillance_log(log_text: str) -> pd.DataFrame:
    """
    Parse raw surveillance log text into a clean pandas DataFrame.
    Idempotent: same input yields same output. Handles variable columns and missing fields.
    """
    lines = [ln.strip() for ln in log_text.strip().splitlines() if ln.strip()]
    if not lines:
        return pd.DataFrame(columns=CANONICAL_COLUMNS)

    # First line = header
    header_line = lines[0]
    expected_columns = _infer_columns_from_header(header_line)
    if "local_timestamp" not in expected_columns:
        expected_columns.insert(0, "local_timestamp")
    if "integrity_hash" not in expected_columns:
        expected_columns.append("integrity_hash")

    rows = []
    parse_errors = []
    for idx, line in enumerate(lines[1:], start=2):
        if line.startswith("timestamp") or line.startswith("date,"):
            continue
        try:
            parsed = _parse_data_line(line, expected_columns)
            if parsed is not None:
                rows.append(parsed)
        except Exception as e:
            parse_errors.append((idx, str(e)))
            # Still try to yield a minimal row so we don't drop the line
            try:
                parsed = _parse_data_line(line, expected_columns)
                if parsed is not None:
                    rows.append(parsed)
            except Exception:
                pass

    if parse_errors and os.environ.get("SURVEILLANCE_LOG_VERBOSE", ""):
        warnings.warn(f"Parse issues on lines: {[p[0] for p in parse_errors]}")

    if not rows:
        return pd.DataFrame(columns=expected_columns)

    # Normalize to canonical columns
    all_cols = list(CANONICAL_COLUMNS)
    for c in expected_columns:
        if c not in all_cols:
            all_cols.append(c)
    df = pd.DataFrame(rows)
    for c in all_cols:
        if c not in df.columns:
            df[c] = None
    df = df[[c for c in all_cols if c in df.columns]]

    for col in ("local_timestamp", "timestamp_utc"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].apply(
                lambda x: None if x is None or str(x).strip().lower() in NULL_VALUES else str(x).strip()
            )

    return df


# -----------------------------------------------------------------------------
# Data quality & summary
# -----------------------------------------------------------------------------


def print_data_quality(df: pd.DataFrame) -> None:
    """Print shape, dtypes, missing % per column, and key value counts."""
    print("\n" + "=" * 60 + "\nDATA QUALITY & SUMMARY\n" + "=" * 60)
    print(f"Shape: {df.shape[0]} rows x {df.shape[1]} columns")
    print("\nDtypes:")
    print(df.dtypes.to_string())
    print("\nMissing % per column:")
    missing = (df.isna().sum() / len(df) * 100).round(1)
    for c in df.columns:
        print(f"  {c}: {missing[c]}%")
    print("\n--- Value counts (key columns) ---")
    for col in ("object", "scene", "event"):
        if col in df.columns:
            print(f"\n{col}:")
            print(df[col].value_counts(dropna=False).head(15).to_string())


def report_duplicates(df: pd.DataFrame) -> None:
    """Detect and report duplicate lines by timestamp + hash."""
    key_cols = [c for c in ("local_timestamp", "integrity_hash") if c in df.columns]
    if not key_cols:
        return
    dup = df.duplicated(subset=key_cols, keep=False)
    n_dup = dup.sum()
    print(f"\nDuplicate lines (by timestamp + integrity_hash): {n_dup}")


def summarize_activity(df: pd.DataFrame) -> dict[str, Any]:
    """Summarize activity: hours covered, peak times, unique persons proxy, loitering count."""
    summary = {}
    ts = df.get("local_timestamp")
    if ts is not None and ts.notna().any():
        ts = pd.to_datetime(ts, errors="coerce").dropna()
        if len(ts) >= 2:
            span = ts.max() - ts.min()
            summary["total_hours_covered"] = span.total_seconds() / 3600
            summary["first_ts"] = ts.min()
            summary["last_ts"] = ts.max()
        else:
            summary["total_hours_covered"] = 0
    else:
        summary["total_hours_covered"] = 0
    if "event" in df.columns:
        ev = df["event"].astype(str).str.lower()
        summary["loitering_count"] = int(ev.str.contains("loitering", na=False).sum())
    else:
        summary["loitering_count"] = 0
    person = df.get("object")
    if person is not None:
        person_mask = person.astype(str).str.lower() == "person"
        sub = df.loc[person_mask, ["clothing_description", "estimated_height_cm"]].dropna(how="all")
        summary["unique_person_proxy"] = sub.drop_duplicates().shape[0]
    else:
        summary["unique_person_proxy"] = 0
    if ts is not None and len(ts):
        summary["peak_hour"] = int(ts.dt.hour.mode().iloc[0]) if len(ts.dt.hour.mode()) else None
    else:
        summary["peak_hour"] = None
    return summary


# -----------------------------------------------------------------------------
# Analysis: value over time, time deltas, signatures, tracks, correlations
# -----------------------------------------------------------------------------


def add_value_and_tracks(df: pd.DataFrame, value_col: str = "estimated_height_cm", track_gap_sec: float = 30.0) -> pd.DataFrame:
    """Add 'value' (alias of numeric column after hair_color), time_since_prev, and is_track_continuation."""
    out = df.copy()
    if value_col in out.columns:
        out["value"] = pd.to_numeric(out[value_col], errors="coerce")
    else:
        out["value"] = np.nan
    ts = pd.to_datetime(out["local_timestamp"], errors="coerce")
    out = out.sort_values("local_timestamp").reset_index(drop=True)
    ts = ts.iloc[out.index]
    delta = ts.diff().dt.total_seconds()
    out["time_since_prev"] = delta
    out["is_track_continuation"] = (delta.notna() & (delta < track_gap_sec)).astype(bool)
    return out


def run_analysis(df: pd.DataFrame, output_dir: str = ".", save_plots: bool = True) -> dict[str, Any]:
    """Run full analysis: plots, stats, clusters. Returns dict of stats and paths."""
    stats = {}
    if df.empty:
        return stats
    df = add_value_and_tracks(df)

    # Numeric stats for value
    if "value" in df.columns and df["value"].notna().any():
        stats["value_mean"] = float(df["value"].mean())
        stats["value_median"] = float(df["value"].median())
        stats["value_min"] = float(df["value"].min())
        stats["value_max"] = float(df["value"].max())
    if "time_since_prev" in df.columns:
        valid = df["time_since_prev"].dropna()
        valid = valid[valid > 0]
        if len(valid):
            stats["median_time_delta_sec"] = float(valid.median())
    if "is_track_continuation" in df.columns:
        stats["track_continuations"] = int(df["is_track_continuation"].sum())

    # Mean/median value per location
    if "scene" in df.columns and "value" in df.columns:
        by_scene = df.groupby("scene", dropna=False)["value"].agg(["mean", "median", "count"])
        stats["value_by_location"] = by_scene.to_dict()

    # Motion type frequency
    if "event" in df.columns:
        ev = df["event"].astype(str).str.lower()
        stats["motion_passing_or_motion"] = int(ev.str.contains("motion", na=False).sum())
        stats["motion_unknown_or_none"] = int(ev.isin(["", "none", "nan"]).sum() + ev.isna().sum())
        stats["motion_loitering"] = int(ev.str.contains("loitering", na=False).sum())

    if not HAS_PLOT or not save_plots:
        return stats

    os.makedirs(output_dir, exist_ok=True)

    # Plot 1: value over time, colored by location or hair_color
    ts = pd.to_datetime(df["local_timestamp"], errors="coerce")
    color_col = "scene" if "scene" in df.columns else "hair_color"
    if color_col in df.columns and df["value"].notna().any():
        fig, ax = plt.subplots(figsize=(10, 4))
        for key in df[color_col].dropna().unique():
            mask = df[color_col] == key
            ax.scatter(ts[mask], df.loc[mask, "value"], label=str(key), alpha=0.7, s=20)
        ax.set_xlabel("Timestamp")
        ax.set_ylabel("Value (e.g. height_cm / bbox_px)")
        ax.set_title("Value over time by " + color_col)
        ax.legend()
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        fig.tight_layout()
        path1 = os.path.join(output_dir, "value_over_time.png")
        fig.savefig(path1, dpi=100)
        plt.close()
        stats["plot_value_over_time"] = path1

    # Plot 2: Detections per 1-minute bin, colored by indoor/outdoor
    if "local_timestamp" in df.columns:
        df_temp = df.set_index(pd.to_datetime(df["local_timestamp"], errors="coerce")).dropna(how="all", subset=["local_timestamp"])
        if not df_temp.empty:
            df_temp["scene_cat"] = df_temp.get("scene", pd.Series(dtype=object)).fillna("unknown")
            minutely = df_temp.groupby([df_temp.index.floor("1min"), "scene_cat"]).size().unstack(fill_value=0)
            fig, ax = plt.subplots(figsize=(12, 4))
            # Use integer x and label with time strings to avoid Period/freq issues
            x_labels = [t.strftime("%H:%M") for t in minutely.index]
            x_pos = range(len(minutely))
            bottom = np.zeros(len(minutely))
            for col in minutely.columns:
                ax.bar(x_pos, minutely[col], bottom=bottom, label=col, width=0.8)
                bottom = bottom + minutely[col].values
            ax.set_xticks(x_pos)
            ax.set_xticklabels(x_labels, rotation=45, ha="right")
            ax.set_xlabel("Time (1-min bins)")
            ax.set_ylabel("Detections")
            ax.set_title("Detections per 1-minute bin by location")
            ax.legend(title="Location")
            fig.tight_layout()
            path2 = os.path.join(output_dir, "detections_per_minute.png")
            fig.savefig(path2, dpi=100)
            plt.close()
            stats["plot_detections_per_minute"] = path2

    # Plot 3: Value distribution (histogram or by motion type)
    if "value" in df.columns and df["value"].notna().any():
        fig, ax = plt.subplots(figsize=(8, 4))
        df["value"].dropna().hist(ax=ax, bins=20, edgecolor="black", alpha=0.7)
        ax.set_xlabel("Value")
        ax.set_ylabel("Count")
        ax.set_title("Distribution of value (e.g. height_cm / bbox)")
        fig.tight_layout()
        path3 = os.path.join(output_dir, "value_distribution.png")
        fig.savefig(path3, dpi=100)
        plt.close()
        stats["plot_value_distribution"] = path3

    # DBSCAN on (value, hair_encoded, clothing_encoded) if enough numeric data
    try:
        from sklearn.cluster import DBSCAN
        X = df[["value"]].copy()
        X["value"] = pd.to_numeric(X["value"], errors="coerce").fillna(X["value"].median())
        if "hair_color" in df.columns:
            hair_enc = df["hair_color"].astype(str).fillna("").map(lambda s: hash(s) % 100)
            X["hair_enc"] = hair_enc
        else:
            X["hair_enc"] = 0
        if "clothing_description" in df.columns:
            cloth_enc = df["clothing_description"].astype(str).fillna("").map(lambda s: hash(s) % 100)
            X["cloth_enc"] = cloth_enc
        else:
            X["cloth_enc"] = 0
        X = X.fillna(X.median())
        if len(X) >= 3:
            clustering = DBSCAN(eps=15, min_samples=2).fit(X)
            n_clusters = len(set(clustering.labels_) - {-1})
            stats["dbscan_estimated_individuals"] = n_clusters
            stats["dbscan_noise_points"] = int((clustering.labels_ == -1).sum())
    except Exception:
        stats["dbscan_estimated_individuals"] = None
        stats["dbscan_noise_points"] = None

    return stats


# -----------------------------------------------------------------------------
# Anomaly detection: sudden hair/clothing change, motion frequency
# -----------------------------------------------------------------------------


def flag_anomalies(df: pd.DataFrame, time_window_sec: float = 60.0) -> pd.DataFrame:
    """Flag rows where hair_color or clothing_description changes within time_window of previous row."""
    out = df.copy()
    out["anomaly_sudden_appearance_change"] = False
    if "local_timestamp" not in out.columns or len(out) < 2:
        return out
    ts = pd.to_datetime(out["local_timestamp"], errors="coerce")
    out = out.sort_values("local_timestamp").reset_index(drop=True)
    ts = ts.iloc[out.index]
    delta = ts.diff().dt.total_seconds()
    for col in ("hair_color", "clothing_description"):
        if col not in out.columns:
            continue
        changed = out[col] != out[col].shift(1)
        within_window = delta.notna() & (delta < time_window_sec) & (delta > 0)
        out.loc[changed & within_window, "anomaly_sudden_appearance_change"] = True
    return out


# -----------------------------------------------------------------------------
# Markdown report
# -----------------------------------------------------------------------------


def export_summary_markdown(
    df: pd.DataFrame,
    summary: dict[str, Any],
    stats: dict[str, Any],
    path: str = "surveillance_analysis_report.md",
    output_dir: str = ".",
) -> None:
    """Write Markdown report: data quality, field meanings, interpretation, plot refs, recommendations."""
    with open(path, "w") as f:
        f.write("# Surveillance log analysis report\n\n")
        f.write("## Data quality summary\n\n")
        f.write(f"- **Total rows:** {len(df)}\n")
        f.write(f"- **Hours covered:** {summary.get('total_hours_covered', 0):.1f}\n")
        f.write(f"- **Missing key fields:** ")
        missing = []
        for c in ("object", "scene", "event", "local_timestamp"):
            if c in df.columns and df[c].isna().all():
                missing.append(c)
        f.write(", ".join(missing) if missing else "None critical.\n")
        f.write("\n")
        f.write("## Most likely field meanings (evidence)\n\n")
        f.write("- **value / estimated_height_cm:** 3-digit number after hair_color. ")
        f.write("In sample, clusters 170–178; indoor often ~170–172, outdoor 178. ")
        f.write("Could be height_cm, bbox height px, or confidence×100; stability indoors suggests fixed camera/distance.\n\n")
        f.write("- **hair_color, clothing_description:** From parser keyword matching (gray, brown, dark, top/body).\n\n")
        f.write("- **timestamp_utc / local_timestamp:** Parsed from leading M/D/YY H:MM:SS and trailing ISO UTC.\n\n")
        f.write("## Revised interpretation of events\n\n")
        f.write("Likely 1–2 subjects transiting; indoor cluster suggests entry/exit. ")
        f.write("Value stability indoors may indicate fixed camera distance estimation rather than true height. ")
        f.write("Recommend cross-check with YOLO/Frigate docs for attribute semantics.\n\n")
        f.write("## Key visuals\n\n")
        for key in ("plot_value_over_time", "plot_detections_per_minute", "plot_value_distribution"):
            if stats.get(key):
                name = Path(stats[key]).name
                f.write(f"- ![{name}]({name})\n\n")
        f.write("## Recommendations\n\n")
        f.write("- If this is YOLO attribute output, cross-check with official Ultralytics/Frigate docs for column semantics.\n")
        f.write("- Emit JSON Lines per event for reliable parsing and audit.\n")
        f.write("- Add camera_id and model_version to each line for multi-camera correlation.\n")
    print(f"Saved: {path}")


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main() -> None:
    """Load log, parse, analyze, export cleaned CSV and report."""
    log_path = os.environ.get("SURVEILLANCE_LOG_PATH")
    if log_path and Path(log_path).is_file():
        with open(log_path, encoding="utf-8", errors="replace") as f:
            log_text = f.read()
        print(f"Loaded log from {log_path} ({len(log_text)} chars)")
    else:
        log_text = SAMPLE_RAW_LOG
        print("Using embedded SAMPLE_RAW_LOG (set SURVEILLANCE_LOG_PATH to use a file)")

    df = parse_surveillance_log(log_text)
    if df.empty:
        print("No data parsed. Check log format.")
        return

    # Add value alias for analysis
    df = add_value_and_tracks(df)
    df = flag_anomalies(df)

    print_data_quality(df)
    report_duplicates(df)
    summary = summarize_activity(df)
    print("\n--- Activity summary ---")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    print("\n--- df.head(10) ---")
    print(df.head(10).to_string())
    print("\n--- df.info() ---")
    df.info()
    print("\n--- df.describe() (numeric) ---")
    print(df.describe(include=[np.number]).to_string())
    print("\n--- Unique categorical (object, scene, event, hair_color) ---")
    for col in ("object", "scene", "event", "hair_color"):
        if col in df.columns:
            print(f"{col}: {df[col].dropna().unique().tolist()}")

    out_csv = "cleaned_logs.csv"
    df.to_csv(out_csv, index=False)
    print(f"\nSaved DataFrame to {out_csv}")
    # Also save for dashboard (surveillance_log_clean.csv)
    try:
        dash_csv = os.path.join(os.path.dirname(__file__) or ".", "..", "surveillance_log_clean.csv")
        dash_csv = os.path.abspath(dash_csv)
        df.to_csv(dash_csv, index=False)
        print(f"Also saved to {dash_csv}")
    except Exception:
        pass

    output_dir = os.path.dirname(out_csv) or "."
    stats = run_analysis(df, output_dir=output_dir, save_plots=HAS_PLOT)
    print("\n--- Analysis stats ---")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    export_summary_markdown(df, summary, stats, path="surveillance_analysis_report.md", output_dir=output_dir)
    print("Done.")


if __name__ == "__main__":
    main()
