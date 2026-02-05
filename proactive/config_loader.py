"""Load config from config.yaml (or env override)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    """Load YAML config; return dict. Empty dict if no file or PyYAML missing."""
    p = Path(path) if path else CONFIG_PATH
    if not p.is_file():
        return _default_config()
    try:
        import yaml
        with open(p, encoding="utf-8") as f:
            out = yaml.safe_load(f) or {}
    except ImportError:
        out = {}
    return {**_default_config(), **out}


def _default_config() -> dict[str, Any]:
    return {
        "database": {"path": ""},
        "camera": {"source": 0, "width": 640, "height": 480},
        "parser": {"log_path": "", "encoding": "utf-8"},
        "reid": {"enabled": True, "similarity_threshold": 0.85, "embedding_backend": "auto"},
        "predictor": {
            "loiter_duration_sec": 300,
            "night_start_hour": 22,
            "night_end_hour": 6,
            "anomaly_high": 0.5,
            "use_isolation_forest": True,
        },
        "deterrence": {
            "enabled": False,
            "threat_thresholds": {"low": 20, "medium": 40, "high": 70},
            "script_path": "",
            "webhook_url": "",
            "voice_warning": False,
            "voice_text": "You are being recorded. Leave the area now.",
        },
        "audio": {"enabled": False},
        "viz": {
            "detections_per_hour_path": "detections_per_hour.png",
            "timeline_path": "timeline.png",
            "report_md_path": "surveillance_summary_report.md",
        },
        "retention_days": 90,
    }
