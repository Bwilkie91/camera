"""
Predictive intent & threat: rule-based + lightweight ML.

- Rules: loitering > 5 min + nighttime + unknown person + high anomaly → high threat.
- ML: Isolation Forest (or small LSTM sketch) on track features: dwell time,
  position delta, direction, crowd changes → suspicious intent score.
- Output: predicted_intent (passing / scouting / aggressive / normal),
  escalated threat_score. Edge-only; no cloud.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np

# Optional sklearn for Isolation Forest
try:
    from sklearn.ensemble import IsolationForest
    SKLEARN_AVAILABLE = True
except ImportError:
    IsolationForest = None
    SKLEARN_AVAILABLE = False

# Intent labels for explainability
INTENT_PASSING = "passing"
INTENT_SCOUTING = "scouting"
INTENT_AGGRESSIVE = "aggressive"
INTENT_NORMAL = "normal"
INTENT_UNKNOWN = "unknown"


@dataclass
class IntentPrediction:
    """Single prediction for a track or event."""
    intent: str
    intent_probs: dict[str, float]
    threat_score: float
    is_anomaly: bool
    rule_flags: list[str]


# ---- Rule-based escalation ----
def _is_nighttime(ts: datetime | str, hour_night_start: int = 22, hour_night_end: int = 6) -> bool:
    """True if timestamp is in nighttime window (e.g. 22:00–06:00)."""
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return False
    h = ts.hour
    if hour_night_start > hour_night_end:
        return h >= hour_night_start or h < hour_night_end
    return hour_night_start <= h < hour_night_end


def rule_based_threat(
    dwell_seconds: float,
    timestamp_utc: datetime | str,
    event: str | None,
    anomaly_score: float | None,
    person_id: int | None,
    threat_score_in: float | None,
    *,
    loiter_duration_threshold_sec: float = 300.0,
    night_start: int = 22,
    night_end: int = 6,
    anomaly_high: float = 0.5,
) -> tuple[float, list[str]]:
    """
    Rule-based threat escalation. Returns (escalated_threat_score, list of rule flags).
    """
    flags: list[str] = []
    score = float(threat_score_in or 0.0)

    is_loitering = event and "loitering" in str(event).lower()
    if is_loitering and dwell_seconds >= loiter_duration_threshold_sec:
        flags.append("loitering_long")
        score = max(score, 40.0)
    if _is_nighttime(timestamp_utc, night_start, night_end):
        flags.append("nighttime")
        if is_loitering:
            score = max(score, 50.0)
    if person_id is None and is_loitering:
        flags.append("unknown_person_loitering")
        score = max(score, 35.0)
    if anomaly_score is not None and anomaly_score >= anomaly_high:
        flags.append("high_anomaly")
        score = max(score, 30.0)
    if "loitering_long" in flags and "nighttime" in flags and "unknown_person" in str(flags):
        score = max(score, 75.0)
        flags.append("high_risk_combination")

    return min(score, 100.0), flags


def extract_track_features(track: dict[str, Any]) -> np.ndarray:
    """
    Extract a fixed-size feature vector for ML from a track dict.
    Used by Isolation Forest for anomaly / intent scoring.
    """
    dwell = float(track.get("dwell_seconds") or 0)
    count = int(track.get("detection_count") or 0)
    threat_max = float(track.get("threat_score_max") or 0)
    anomaly_max = float(track.get("anomaly_score_max") or 0)
    # Normalize to similar scale
    return np.array([
        min(dwell / 3600.0, 2.0),
        min(count / 50.0, 2.0),
        threat_max / 100.0,
        min(anomaly_max, 2.0),
        1.0 if track.get("scene") == "Outdoor" else 0.0,
    ], dtype=np.float32)


def predict_intent_forest(
    track: dict[str, Any],
    forest: "IsolationForest | None",
    feature_vectors: np.ndarray | None,
) -> IntentPrediction:
    """
    Hybrid: rules + Isolation Forest anomaly. If forest is fitted, use it;
    else use rules only. intent_probs are derived from rules and anomaly score.
    """
    flags: list[str] = []
    dwell = float(track.get("dwell_seconds") or 0)
    ts = track.get("start_utc") or track.get("end_utc")
    event = track.get("event")  # might be on first event
    anomaly_max = float(track.get("anomaly_score_max") or 0)
    threat_max = float(track.get("threat_score_max") or 0)
    person_id = track.get("person_id")

    escalated, rule_flags = rule_based_threat(
        dwell, ts, event, anomaly_max, person_id, threat_max,
    )
    flags.extend(rule_flags)

    # Isolation Forest: -1 = anomaly, 1 = normal
    is_anomaly = False
    if SKLEARN_AVAILABLE and forest is not None and feature_vectors is not None:
        feat = extract_track_features(track).reshape(1, -1)
        pred = forest.predict(feat)
        if pred[0] < 0:
            is_anomaly = True
            flags.append("ml_anomaly")
        score_forest = forest.decision_function(feat)[0] if hasattr(forest, "decision_function") else 0.0
        if score_forest < -0.1:
            escalated = max(escalated, 25.0)

    # Intent labels from rules
    if "high_risk_combination" in flags or escalated >= 70:
        intent = INTENT_AGGRESSIVE
    elif "scouting" in str(flags).lower() or (dwell > 120 and person_id is None):
        intent = INTENT_SCOUTING
    elif dwell < 60 and threat_max < 20:
        intent = INTENT_PASSING
    else:
        intent = INTENT_NORMAL if not is_anomaly else INTENT_SCOUTING

    # Simple prob distribution
    probs = {INTENT_PASSING: 0.0, INTENT_SCOUTING: 0.0, INTENT_AGGRESSIVE: 0.0, INTENT_NORMAL: 0.0}
    probs[intent] = 0.7
    for k in probs:
        if k != intent:
            probs[k] = 0.1

    return IntentPrediction(
        intent=intent,
        intent_probs=probs,
        threat_score=escalated,
        is_anomaly=is_anomaly,
        rule_flags=flags,
    )


def fit_isolation_forest(tracks: list[dict[str, Any]], n_estimators: int = 100) -> "IsolationForest | None":
    """Fit Isolation Forest on track features for anomaly detection."""
    if not SKLEARN_AVAILABLE or not tracks:
        return None
    X = np.vstack([extract_track_features(t) for t in tracks])
    clf = IsolationForest(n_estimators=n_estimators, random_state=42, contamination=0.1)
    clf.fit(X)
    return clf
