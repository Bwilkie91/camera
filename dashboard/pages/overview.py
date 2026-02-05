"""
Overview: KPI cards, heatmap (hour x day), occupancy trend, threat/anomaly summary.
Enterprise: at-a-glance health, color-coded severity.
"""
from __future__ import annotations

from dash import dcc, html
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


def kpi_cards(df: pd.DataFrame) -> html.Div:
    if df is None or df.empty:
        return dbc.Row([dbc.Col(html.Div("No data", className="text-muted"))])
    total = len(df)
    ts_col = "timestamp_local" if "timestamp_local" in df.columns else "local_timestamp"
    if ts_col not in df.columns:
        ts_col = "timestamp_utc"
    ev = df.get("event")
    loiter = (ev.astype(str).str.lower().str.contains("loitering", na=False)).sum() if ev is not None else 0
    threat = df.get("threat_score")
    high_threat = (pd.to_numeric(threat, errors="coerce").fillna(0) > 0).sum() if threat is not None else 0
    persons = (df["object"].astype(str).str.lower() == "person").sum() if "object" in df.columns else 0
    return dbc.Row(
        [
            dbc.Col(
                dbc.Card([dbc.CardBody([html.H5("Total events", className="card-title"), html.H4(total, id="kpi-total")])], className="kpi-card shadow-sm"),
                md=3,
            ),
            dbc.Col(
                dbc.Card([dbc.CardBody([html.H5("Loitering", className="card-title"), html.H4(loiter, id="kpi-loiter", style={"color": "var(--vigil-anomaly)"})])], className="kpi-card card-loiter shadow-sm"),
                md=3,
            ),
            dbc.Col(
                dbc.Card([dbc.CardBody([html.H5("High threat", className="card-title"), html.H4(high_threat, id="kpi-threat", style={"color": "var(--vigil-threat)"})])], className="kpi-card card-threat shadow-sm"),
                md=3,
            ),
            dbc.Col(
                dbc.Card([dbc.CardBody([html.H5("Person detections", className="card-title"), html.H4(persons, id="kpi-persons", style={"color": "var(--vigil-success)"})])], className="kpi-card card-success shadow-sm"),
                md=3,
            ),
        ],
        className="g-3 mb-4",
    )


def heatmap_figure(df: pd.DataFrame) -> go.Figure:
    if df is None or df.empty:
        return go.Figure().add_annotation(text="No data", x=0.5, y=0.5, showarrow=False)
    ts_col = "timestamp_local" if "timestamp_local" in df.columns else "local_timestamp"
    if ts_col not in df.columns:
        ts_col = "timestamp_utc"
    df = df.copy()
    df["ts"] = pd.to_datetime(df[ts_col], errors="coerce")
    df = df.dropna(subset=["ts"])
    if df.empty:
        return go.Figure().add_annotation(text="No data", x=0.5, y=0.5, showarrow=False)
    df["hour"] = df["ts"].dt.hour
    df["dow"] = df["ts"].dt.dayofweek
    agg = df.groupby(["dow", "hour"]).size().reset_index(name="count")
    pivot = agg.pivot(index="dow", columns="hour", values="count").fillna(0).reindex(index=range(7), columns=range(24), fill_value=0)
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=[f"{h}:00" for h in range(24)],
        y=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        colorscale=[[0, "rgba(15, 23, 42, 0.8)"], [0.4, "#1e40af"], [0.8, "#2563eb"], [1, "#93c5fd"]],
        hoverongaps=False,
    ))
    fig.update_layout(
        title="Detections by hour and day of week",
        xaxis_title="Hour",
        yaxis_title="Day",
        margin=dict(t=36, r=16, b=36, l=48),
        height=300,
        font=dict(color="#94a3b8", size=11),
        title_font=dict(size=14, color="#e2e8f0"),
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(30, 41, 59, 0.4)",
        xaxis=dict(gridcolor="rgba(148, 163, 184, 0.12)", zerolinecolor="rgba(148, 163, 184, 0.2)"),
        yaxis=dict(gridcolor="rgba(148, 163, 184, 0.12)", zerolinecolor="rgba(148, 163, 184, 0.2)"),
    )
    return fig


def occupancy_figure(df: pd.DataFrame) -> go.Figure:
    if df is None or df.empty:
        return go.Figure().add_annotation(text="No data", x=0.5, y=0.5, showarrow=False)
    ts_col = "timestamp_local" if "timestamp_local" in df.columns else "local_timestamp"
    if ts_col not in df.columns:
        ts_col = "timestamp_utc"
    df = df.copy()
    df["ts"] = pd.to_datetime(df[ts_col], errors="coerce")
    df = df.dropna(subset=["ts"])
    if "crowd_count" not in df.columns:
        df["crowd_count"] = 1
    df = df.set_index("ts").sort_index()
    hourly = df["crowd_count"].resample("h").sum()
    fig = go.Figure(data=go.Scatter(x=hourly.index, y=hourly.values, mode="lines+markers", fill="tozeroy", line=dict(color="#2563eb", width=2), marker=dict(size=4)))
    fig.update_layout(
        title="Crowd / occupancy over time",
        xaxis_title="Time",
        yaxis_title="Count",
        margin=dict(t=36, r=16, b=36, l=48),
        height=280,
        font=dict(color="#94a3b8", size=11),
        title_font=dict(size=14, color="#e2e8f0"),
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(30, 41, 59, 0.4)",
        xaxis=dict(gridcolor="rgba(148, 163, 184, 0.12)", zerolinecolor="rgba(148, 163, 184, 0.2)"),
        yaxis=dict(gridcolor="rgba(148, 163, 184, 0.12)", zerolinecolor="rgba(148, 163, 184, 0.2)"),
        hovermode="x unified",
    )
    return fig


def _last_seen_str(utc_iso: str | None) -> str:
    """Format last_frame_utc as 'Just now', 'Nm ago', or '—'."""
    if not utc_iso:
        return "—"
    try:
        from datetime import datetime, timezone
        ts = datetime.fromisoformat(utc_iso.replace("Z", "+00:00")).timestamp()
        sec = int(datetime.now(timezone.utc).timestamp() - ts)
        if sec < 60:
            return "Just now"
        if sec < 3600:
            return f"{sec // 60}m ago"
        return f"{sec // 3600}h ago"
    except Exception:
        return "—"


def system_status_cards(status: dict | None) -> html.Div:
    """Build System Status & Network Health block from Vigil API (Flask/React-style). Shown when data.source is api."""
    if not status:
        return html.Div()
    rec = "REC" if status.get("recording") else "—"
    db_ok = status.get("db_ok", False)
    uptime_s = status.get("uptime_seconds", 0)
    uptime_str = f"{uptime_s // 3600}h {(uptime_s % 3600) // 60}m" if uptime_s else "—"
    cameras = status.get("cameras") or []
    status_class = "text-success" if status.get("status") == "ok" else "text-warning"
    def _last_offline_str(c: dict) -> str:
        utc = c.get("last_offline_utc")
        if not utc:
            return "—"
        ls = _last_seen_str(utc)  # reuse same relative time
        if c.get("status") == "ok":
            return f"{ls} ago"
        return f"since {ls} ago"

    cam_items = []
    for c in cameras:
        parts = [f"{c.get('name', c.get('id', '?'))}: {c.get('status', '?')}", c.get("resolution") or "—", f"last seen: {_last_seen_str(c.get('last_frame_utc'))}", f"last offline: {_last_offline_str(c)}"]
        if c.get("flapping"):
            parts.append("(flapping)")
        cam_items.append(" — ".join(parts))
    return html.Div(
        [
            html.H6("System status (Vigil API)", className="mb-2"),
            dbc.Row(
                [
                    dbc.Col(dbc.Card([dbc.CardBody([html.H6("Recording", className="card-title small"), html.Span(rec, className="text-danger fw-bold")])], className="shadow-sm"), md=2),
                    dbc.Col(dbc.Card([dbc.CardBody([html.H6("DB", className="card-title small"), html.Span("OK" if db_ok else "Error", className="text-success" if db_ok else "text-danger")])], className="shadow-sm"), md=2),
                    dbc.Col(dbc.Card([dbc.CardBody([html.H6("Uptime", className="card-title small"), html.Span(uptime_str)])], className="shadow-sm"), md=2),
                    dbc.Col(dbc.Card([dbc.CardBody([html.H6("Cameras", className="card-title small"), html.Span(len(cameras))])], className="shadow-sm"), md=2),
                    dbc.Col(dbc.Card([dbc.CardBody([html.H6("Status", className="card-title small"), html.Span(status.get("status", "—"), className=status_class)])], className="shadow-sm"), md=2),
                ],
                className="g-2 mb-2",
            ),
            html.Details([
                html.Summary("Camera list", className="small text-muted"),
                html.Ul([html.Li(t, className="small") for t in cam_items], className="small mt-1 mb-0"),
            ], className="mb-3"),
        ]
    )


def layout(data_store_id: str = "filtered-data-store") -> html.Div:
    return html.Div(
        [
            html.Div(id="overview-kpis"),
            dbc.Button([html.I(className="bi bi-download me-1"), "Export filtered data (CSV)"], id="overview-export-csv", size="sm", color="secondary", outline=True, className="mb-3"),
            html.Div(id="overview-system-status", children=[]),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card([dbc.CardBody(dcc.Graph(id="overview-heatmap", config={"displayModeBar": True, "displaylogo": False, "toImageButtonOptions": {"format": "png"}}))], className="overflow-hidden"),
                        md=6,
                        className="mb-3",
                    ),
                    dbc.Col(
                        dbc.Card([dbc.CardBody(dcc.Graph(id="overview-occupancy", config={"displayModeBar": True, "displaylogo": False, "toImageButtonOptions": {"format": "png"}}))], className="overflow-hidden"),
                        md=6,
                        className="mb-3",
                    ),
                ],
                className="g-3",
            ),
        ]
    )
