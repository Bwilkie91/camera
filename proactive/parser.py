"""
Parser: raw log → clean DataFrame + optional SQLite ingestion.

Reuses the existing surveillance_log_parser logic (same semi-structured format).
Exposes parse_surveillance_log() and helpers to load from file/string and
normalize all fields for downstream ReID, predictor, and DB.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Reuse existing parser from project scripts (load by path so it works from any cwd)
_parser_path = Path(__file__).resolve().parent.parent / "scripts" / "surveillance_log_parser.py"
_parse_log = None
if _parser_path.exists():
    import importlib.util
    _spec = importlib.util.spec_from_file_location("surveillance_log_parser", _parser_path)
    if _spec and _spec.loader:
        _mod = importlib.util.module_from_spec(_spec)
        sys.modules["surveillance_log_parser"] = _mod
        _spec.loader.exec_module(_mod)
        _parse_log = getattr(_mod, "parse_surveillance_log", None)


def parse_surveillance_log(log_text: str):
    """
    Parse raw surveillance log text into a clean pandas DataFrame.
    Columns: local_timestamp, timestamp_utc, object, scene, event, crowd_count,
    threat_score, anomaly_score, clothing_description, estimated_height_cm, etc.
    """
    if _parse_log is None:
        raise ImportError("surveillance_log_parser not found; add project root to PYTHONPATH")
    return _parse_log(log_text)


def load_log_from_path(path: str | Path) -> str:
    """Load raw log file as string."""
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def parse_log_file(path: str | Path):
    """Load and parse a log file; returns DataFrame."""
    return parse_surveillance_log(load_log_from_path(path))
