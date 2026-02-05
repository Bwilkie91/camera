"""
Alerts & Anomalies: threat distribution, anomaly vs time scatter, high-threat/loitering list.
"""
from __future__ import annotations

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


def threat_distribution_figure(df: pd.DataFrame) -> go.Figure:
    if df is None or df.empty or "threat_score" not in df.columns:
        return go.Figure().add_annotation(text="No data", x=0.5, y=0.5, showarrow=False)
    s = pd.to_numeric(df["threat_score"], errors="coerce").fillna(0)
    bins = [0, 0.5, 20, 50, 100]
    labels = ["0", "1-20", "21-50", "51+"]
    s_bin = pd.cut(s, bins=bins, labels=labels, include_lowest=True).value_counts().sort_index()
    fig = go.Figure(data=go.Bar(
        x=s_bin.index.astype(str), y=s_bin.values,
        marker_color=["#0d9488", "#eab308", "#d97706", "#dc2626"],
    ))
    fig.update_layout(
        title="Threat score distribution",
        xaxis_title="Threat level",
        yaxis_title="Count",
        margin=dict(t=36, r=16, b=36, l=48),
        height=260,
        font=dict(color="#94a3b8", size=11),
        title_font=dict(size=14, color="#e2e8f0"),
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(30, 41, 59, 0.4)",
        xaxis=dict(gridcolor="rgba(148, 163, 184, 0.12)"),
        yaxis=dict(gridcolor="rgba(148, 163, 184, 0.12)"),
    )
    return fig


def anomaly_scatter_figure(df: pd.DataFrame) -> go.Figure:
    if df is None or df.empty:
        return go.Figure().add_annotation(text="No data", x=0.5, y=0.5, showarrow=False)
    ts_col = "timestamp_local" if "timestamp_local" in df.columns else "local_timestamp"
    if ts_col not in df.columns:
        ts_col = "timestamp_utc"
    df = df.copy()
    df["ts"] = pd.to_datetime(df[ts_col], errors="coerce")
    df = df.dropna(subset=["ts"])
    if "anomaly_score" not in df.columns:
        df["anomaly_score"] = 0
    df["anomaly_score"] = pd.to_numeric(df["anomaly_score"], errors="coerce").fillna(0)
    color_col = None
    if "threat_score" in df.columns:
        df["threat_score"] = pd.to_numeric(df["threat_score"], errors="coerce").fillna(0)
        color_col = "threat_score"
    fig = px.scatter(df.head(500), x="ts", y="anomaly_score", color=color_col,
                     color_continuous_scale=[[0, "#1e293b"], [0.5, "#d97706"], [1, "#dc2626"]],
                     title="Anomaly score over time")
    fig.update_layout(
        margin=dict(t=36, r=16, b=36, l=48),
        height=300,
        font=dict(color="#94a3b8", size=11),
        title_font=dict(size=14, color="#e2e8f0"),
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(30, 41, 59, 0.4)",
        xaxis=dict(gridcolor="rgba(148, 163, 184, 0.12)"),
        yaxis=dict(gridcolor="rgba(148, 163, 184, 0.12)"),
        hovermode="closest",
    )
    return fig


def layout() -> html.Div:
    return html.Div(
        [
            html.P("Data uses global filters and refreshes with the header Refresh or on the polling interval.", className="text-muted small mb-3"),
            dbc.Row(
                [
                    dbc.Col(dbc.Card([dbc.CardBody(dcc.Graph(id="alerts-threat-dist", config={"displaylogo": False}))], className="overflow-hidden"), md=6, className="mb-3"),
                    dbc.Col(dbc.Card([dbc.CardBody(dcc.Graph(id="alerts-anomaly-scatter", config={"displaylogo": False}))], className="overflow-hidden"), md=6, className="mb-3"),
                ],
                className="g-3",
            ),
            dbc.Card(
                [
                    dbc.CardHeader(
                        [
                            html.I(className="bi bi-exclamation-triangle me-2"),
                            "High-threat & loitering events",
                            dbc.Button([html.I(className="bi bi-download me-1"), "Export CSV"], id="alerts-export-csv", size="sm", outline=True, color="primary", className="ms-auto"),
                        ],
                        className="d-flex align-items-center flex-wrap",
                    ),
                    dbc.CardBody(html.Div(id="alerts-high-list")),
                ],
                className="shadow-sm mt-3",
            ),
        ]
    )
