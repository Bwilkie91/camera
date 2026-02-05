"""
Timeline: scrollable event stream / Gantt-like view, color-coded by severity.
Click event → detail modal. Export CSV/JSON/PNG.
"""
from __future__ import annotations

from dash import html, dash_table
import dash_bootstrap_components as dbc
import pandas as pd


def event_table(df: pd.DataFrame, id_prefix: str = "timeline") -> html.Div:
    """DataTable of events with severity styling; click row → modal."""
    if df is None or df.empty:
        return html.Div("No events in selected range.", className="text-muted p-3")
    ts_col = "timestamp_local" if "timestamp_local" in df.columns else "local_timestamp"
    if ts_col not in df.columns:
        ts_col = "timestamp_utc"
    cols_show = [ts_col, "object", "scene", "event", "crowd_count", "threat_score", "anomaly_score", "value", "clothing_description", "anomaly_sudden_appearance_change"]
    cols_show = [c for c in cols_show if c in df.columns]
    slice_df = df[cols_show].head(500)
    for c in slice_df.columns:
        if pd.api.types.is_datetime64_any_dtype(slice_df[c]):
            slice_df[c] = slice_df[c].dt.strftime("%Y-%m-%d %H:%M")
    # Human-readable column names for UI
    _col_names = {
        "local_timestamp": "Time (local)",
        "timestamp_local": "Time (local)",
        "timestamp_utc": "Time (UTC)",
        "anomaly_sudden_appearance_change": "Appearance change",
        "estimated_height_cm": "Height (cm)",
        "clothing_description": "Clothing",
        "crowd_count": "Crowd",
        "threat_score": "Threat",
        "anomaly_score": "Anomaly",
    }
    columns = [{"name": _col_names.get(c, c.replace("_", " ").title()), "id": c} for c in slice_df.columns]
    return html.Div(
        [
            dash_table.DataTable(
                data=slice_df.to_dict("records"),
                columns=columns,
                id=f"{id_prefix}-table",
                row_selectable="single",
                selected_rows=[],
                page_size=25,
                page_action="native",
                style_table={"overflowX": "auto"},
                style_cell={"textAlign": "left", "padding": "8px"},
                style_header={"fontWeight": "bold"},
                style_data_conditional=[
                    {"if": {"filter_query": "{threat_score} > 0"}, "backgroundColor": "rgba(220, 38, 38, 0.12)"},
                    {"if": {"filter_query": "{event} contains 'Loitering'"}, "backgroundColor": "rgba(217, 119, 6, 0.1)"},
                    {"if": {"filter_query": "{anomaly_sudden_appearance_change} = true"}, "backgroundColor": "rgba(251, 191, 36, 0.12)"},
                ],
                export_format="csv",
                export_headers="display",
            ),
        ],
        className="overflow-auto",
    )


def layout() -> html.Div:
    return html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(html.H5("Event timeline", className="mb-0")),
                    dbc.Col(
                        dbc.ButtonGroup(
                            [
                                dbc.Button([html.I(className="bi bi-download me-1"), "CSV"], id="timeline-export-csv", size="sm", outline=True, color="primary"),
                                dbc.Button([html.I(className="bi bi-download me-1"), "JSON"], id="timeline-export-json", size="sm", outline=True, color="primary"),
                            ],
                            className="float-end",
                        ),
                        width="auto",
                    ),
                ],
                className="mb-3 align-items-center justify-content-between",
            ),
            dbc.Card([dbc.CardBody(html.Div(id="timeline-table-container", className="p-0"))], className="shadow-sm overflow-hidden"),
        ]
    )
