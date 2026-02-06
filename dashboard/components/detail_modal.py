"""
Event detail modal: show full record on timeline/table click.
Enterprise: timestamp, object, clothing, threat, hash; no raw dump of PII without need.
Play at moment: link to Vigil UI with ?playback_ts= for recording playback at this time.
"""
from dash import html
import dash_bootstrap_components as dbc


def detail_modal() -> html.Div:
    return dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("Event details"), close_button=True),
            dbc.ModalBody(id="detail-modal-body"),
            dbc.ModalFooter(
                dbc.Button("Close", id="detail-modal-close", className="ms-auto", color="secondary")
            ),
        ],
        id="detail-modal",
        size="lg",
        scrollable=True,
        is_open=False,
    )


def _row_timestamp_iso(row: dict) -> str | None:
    """Get event timestamp as ISO string for playback_ts URL param."""
    for col in ("timestamp_local", "local_timestamp", "timestamp_utc", "date", "time"):
        v = row.get(col)
        if v is None:
            continue
        if hasattr(v, "isoformat"):
            try:
                return v.isoformat().replace(" ", "T")[:23]
            except Exception:
                pass
        if col == "date" and isinstance(v, str):
            t = row.get("time")
            if t is not None:
                return f"{v}T{str(t)[:8]}"
            return f"{v}T00:00:00"
    return None


def build_modal_body(row: dict | None, vigil_ui_base: str | None = None) -> list:
    """Build modal body from a single row (dict). If vigil_ui_base is set, add 'Play at moment' link."""
    if not row:
        return [html.P("No data", className="text-muted")]
    play_link_el = []
    if vigil_ui_base:
        ts_iso = _row_timestamp_iso(row)
        camera_id = row.get("camera_id")
        if ts_iso:
            from urllib.parse import urlencode
            qs = urlencode({"playback_ts": ts_iso, **({"playback_camera_id": str(camera_id)} if camera_id is not None and str(camera_id).strip() else {})})
            href = f"{vigil_ui_base.rstrip('/')}/activity?{qs}"
            play_link_el = [
                html.Div(
                    dbc.Button(
                        [html.I(className="bi bi-play-circle me-2"), "Play at moment"],
                        href=href,
                        target="_blank",
                        rel="noopener noreferrer",
                        color="primary",
                        size="sm",
                        className="mb-3",
                    )
                ),
            ]
    import math
    # Safe keys for display (avoid dumping raw hashes in huge blocks; truncate if needed)
    order = [
        "timestamp_local", "local_timestamp", "timestamp_utc", "object", "scene", "event",
        "crowd_count", "threat_score", "anomaly_score", "value", "time_since_prev",
        "clothing_description", "estimated_height_cm", "perceived_age", "perceived_age_range", "perceived_gender", "perceived_ethnicity", "hair_color", "build", "stress_level",
        "detection_confidence",
        "anomaly_sudden_appearance_change", "gait_notes", "suspicious_behavior", "predicted_intent",
        "integrity_hash", "camera_id", "model_version",
    ]
    items = []
    for k in order:
        v = row.get(k)
        if v is None:
            continue
        if isinstance(v, float):
            if math.isnan(v):
                continue
            v = str(v)
        elif hasattr(v, "isoformat"):
            try:
                v = v.isoformat()
            except Exception:
                v = str(v)
        else:
            v = str(v)
        if k == "integrity_hash" and isinstance(v, str) and len(v) > 24:
            v = v[:24] + "…"
        if k == "anomaly_sudden_appearance_change":
            v = "Yes" if v in ("True", "true", True) else "No"
        label = k.replace("_", " ").title()
        items.append(
            html.Div(
                [html.Strong(label + ": "), v],
                className="mb-1 small",
            )
        )
    return play_link_el + (items if items else [html.P("No fields", className="text-muted")])
