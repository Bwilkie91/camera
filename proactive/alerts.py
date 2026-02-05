"""
Proactive deterrence: escalate response based on threat level.

- If threat > threshold → run configurable actions: script, HomeKit/IFTTT webhook,
  or pyttsx3 voice ("You are being recorded — leave now").
- All local; no cloud. Config-driven thresholds and commands.
"""
from __future__ import annotations

import os
import subprocess
import threading
from typing import Any

# Optional TTS for voice warning
try:
    import pyttsx3
    PYTTSX_AVAILABLE = True
except ImportError:
    pyttsx3 = None
    PYTTSX_AVAILABLE = False

# Debounce: don't fire the same level repeatedly within this many seconds
DEFAULT_DEBOUNCE_SEC = 60


def run_deterrence_script(script_path: str, env: dict[str, str] | None = None) -> bool:
    """Execute a shell script (e.g. turn on lights, siren). Non-blocking."""
    if not script_path or not os.path.isfile(script_path):
        return False
    env = env or {}
    env.setdefault("PROACTIVE_THREAT", "1")
    try:
        subprocess.Popen(
            [script_path],
            env={**os.environ, **env},
            start_new_session=True,
        )
        return True
    except Exception:
        return False


def call_webhook(url: str, method: str = "POST", body: dict | None = None) -> bool:
    """Call IFTTT/HomeKit webhook (e.g. trigger lights/siren)."""
    if not url:
        return False
    try:
        import urllib.request
        import json
        body = body or {"value1": "threat", "source": "vigil_proactive"}
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception:
        return False


def speak_warning(text: str = "You are being recorded. Leave the area now.") -> bool:
    """Use pyttsx3 to speak a warning (edge device)."""
    if not PYTTSX_AVAILABLE:
        return False
    def _speak():
        try:
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception:
            pass
    threading.Thread(target=_speak, daemon=True).start()
    return True


# In-memory debounce: last (level, time)
_last_alert: tuple[float, float] = (0.0, 0.0)


def should_escalate(threat_score: float, config: dict[str, Any], debounce_sec: float = DEFAULT_DEBOUNCE_SEC) -> bool:
    """True if we should run deterrence for this threat_score given config and debounce."""
    import time
    global _last_alert
    thresholds = config.get("deterrence", {}).get("threat_thresholds", {})
    # Levels: low < 30, medium 30–60, high > 60
    if threat_score >= thresholds.get("high", 70):
        level = 3
    elif threat_score >= thresholds.get("medium", 40):
        level = 2
    elif threat_score >= thresholds.get("low", 20):
        level = 1
    else:
        return False
    now = time.time()
    prev_level, prev_time = _last_alert
    if level == prev_level and (now - prev_time) < debounce_sec:
        return False
    _last_alert = (level, now)
    return True


def run_deterrence(threat_score: float, config: dict[str, Any]) -> None:
    """
    Run configured deterrence actions for this threat level.
    Config keys: deterrence.script_path, deterrence.webhook_url, deterrence.voice_warning.
    """
    det = config.get("deterrence", {})
    if not should_escalate(threat_score, config):
        return
    if det.get("script_path"):
        run_deterrence_script(det["script_path"], env={"PROACTIVE_THREAT_SCORE": str(int(threat_score))})
    if det.get("webhook_url"):
        call_webhook(det["webhook_url"], body={"threat_score": threat_score})
    if det.get("voice_warning"):
        speak_warning(det.get("voice_text", "You are being recorded. Leave the area now."))
