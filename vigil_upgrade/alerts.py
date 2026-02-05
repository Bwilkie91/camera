"""
Alerts: console/log + configurable escalation (script, webhook, voice).

Delegates to proactive.alerts when available; otherwise logs only.
"""
from __future__ import annotations

from typing import Any


def run_deterrence(threat_score: float, config: dict[str, Any]) -> None:
    """Run configured deterrence (script, webhook, TTS) if threat exceeds thresholds."""
    try:
        from proactive.alerts import run_deterrence as _run
        _run(threat_score, config)
    except ImportError:
        if threat_score >= (config.get("deterrence", {}).get("threat_thresholds", {}).get("high", 70)):
            print(f"[DETERRENCE] threat_score={threat_score:.0f} — configure proactive.alerts for script/webhook/voice")


def log_alert(message: str, level: str = "info") -> None:
    """Simple console log for alerts."""
    print(f"[{level.upper()}] {message}")
