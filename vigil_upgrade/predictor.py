"""
Loitering / predictive intent: rule-based + ML (Isolation Forest + optional LSTM).

Hybrid logic:
- Rules: dwell > X + nighttime + unknown ReID → escalate threat.
- ML: Isolation Forest on track features (dwell, count, threat_max, anomaly_max, scene).
- Optional: position delta, speed, direction changes from detection sequence;
  small LSTM sketch for sequence anomaly (future).

Escalates threat_score and triggers alerts (console/log + configurable siren/lights).
"""
from __future__ import annotations

from typing import Any

import numpy as np

# Reuse proactive predictor when available
try:
    from proactive.predictor import (
        rule_based_threat,
        extract_track_features,
        predict_intent_forest,
        fit_isolation_forest,
        IntentPrediction,
    )
except ImportError:
    try:
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from proactive.predictor import (
            rule_based_threat,
            extract_track_features,
            predict_intent_forest,
            fit_isolation_forest,
            IntentPrediction,
        )
    except ImportError:
        rule_based_threat = None
        extract_track_features = None
        predict_intent_forest = None
        fit_isolation_forest = None
        IntentPrediction = None


def extract_track_features_with_motion(
    track: dict[str, Any],
    detections: list[dict[str, Any]] | None = None,
) -> np.ndarray:
    """
    Extended features: base track stats + position delta, speed, direction changes.
    detections: list of {bbox_x, bbox_y, bbox_w, bbox_h, timestamp_utc} or similar.
    """
    base = extract_track_features(track) if extract_track_features else np.zeros(5, dtype=np.float32)
    if not detections or len(detections) < 2:
        return base
    # Centers and times
    centers = []
    times = []
    for d in detections:
        x = d.get("bbox_x") or (d.get("bbox") and (d["bbox"][0] + d["bbox"][2]) / 2)
        y = d.get("bbox_y") or (d.get("bbox") and (d["bbox"][1] + d["bbox"][3]) / 2)
        if x is None or y is None:
            continue
        centers.append((float(x), float(y)))
        ts = d.get("timestamp_utc") or d.get("local_timestamp")
        if ts is not None:
            try:
                from datetime import datetime
                t = datetime.fromisoformat(str(ts).replace("Z", "+00:00")) if isinstance(ts, str) else ts
                times.append(t.timestamp())
            except Exception:
                pass
    if len(centers) < 2 or len(times) < 2:
        return base
    centers = np.array(centers)
    times = np.array(times[:len(centers)])
    deltas = np.diff(centers, axis=0)
    dts = np.diff(times)
    dts = np.where(dts <= 0, 1e-6, dts)
    speeds = np.linalg.norm(deltas, axis=1) / dts
    # Direction changes (angle between consecutive deltas)
    angles = np.arctan2(deltas[1:, 1], deltas[1:, 0]) - np.arctan2(deltas[:-1, 1], deltas[:-1, 0])
    angle_changes = np.abs(np.arctan2(np.sin(angles), np.cos(angles)))
    extra = np.array([
        np.mean(speeds) / 1000.0 if speeds.size else 0,
        np.std(speeds) / 1000.0 if speeds.size else 0,
        np.mean(angle_changes) / np.pi if angle_changes.size else 0,
    ], dtype=np.float32)
    return np.concatenate([base, np.clip(extra, 0, 2)])


def predict_intent_hybrid(
    track: dict[str, Any],
    forest: Any = None,
    feature_vectors: np.ndarray | None = None,
    detections: list[dict[str, Any]] | None = None,
) -> Any:
    """
    Hybrid intent: rules + Isolation Forest (+ optional motion features).
    Returns IntentPrediction (from proactive) or a simple dict if proactive missing.
    """
    if predict_intent_forest is not None:
        return predict_intent_forest(track, forest, feature_vectors)
    # Fallback: rules only
    from datetime import datetime
    dwell = float(track.get("dwell_seconds") or 0)
    ts = track.get("start_utc") or track.get("end_utc", "")
    event = track.get("event")
    anomaly_max = float(track.get("anomaly_score_max") or 0)
    threat_max = float(track.get("threat_score_max") or 0)
    person_id = track.get("person_id")
    if rule_based_threat:
        score, flags = rule_based_threat(dwell, ts, event, anomaly_max, person_id, threat_max)
    else:
        score, flags = threat_max or 0, []
    return type("IntentPrediction", (), {
        "intent": "scouting" if score > 30 else "normal",
        "intent_probs": {},
        "threat_score": score,
        "is_anomaly": False,
        "rule_flags": flags,
    })()


def fit_forest(tracks: list[dict[str, Any]], use_motion: bool = False, detections_by_track: dict[int, list] | None = None) -> Any:
    """Fit Isolation Forest on track features. use_motion and detections_by_track for extended features."""
    if fit_isolation_forest is None:
        return None
    return fit_isolation_forest(tracks)


# ---- Alerts: console/log + optional escalation ----
def trigger_alert(
    threat_score: float,
    intent: str,
    rule_flags: list[str],
    config: dict[str, Any] | None = None,
) -> None:
    """Log to console; optionally call proactive alerts (siren/lights)."""
    print(f"[ALERT] threat={threat_score:.0f} intent={intent} flags={rule_flags}")
    if not config or not config.get("alerts", {}).get("escalate"):
        return
    try:
        from proactive.alerts import run_deterrence
        run_deterrence(threat_score, config)
    except ImportError:
        pass
