"""
Persons & Tracks: unique individuals (grouped by clothing/height or ReID stub).
Visit frequency, last seen, typical clothing. Stub for ReID matching display.
"""
from __future__ import annotations

from dash import html, dash_table
import dash_bootstrap_components as dbc
import pandas as pd


def _persons_agg_df(df: pd.DataFrame) -> pd.DataFrame | None:
    """Return aggregated persons DataFrame (visit_count, last_seen, clothing, height_cm) or None."""
    if df is None or df.empty or "object" not in df.columns:
        return None
    persons = df[df["object"].astype(str).str.lower() == "person"].copy()
    if persons.empty:
        return None
    ts_col = "timestamp_local" if "timestamp_local" in persons.columns else "local_timestamp"
    if ts_col not in persons.columns:
        ts_col = "timestamp_utc"
    persons[ts_col] = pd.to_datetime(persons[ts_col], errors="coerce")
    persons = persons.dropna(subset=[ts_col])
    clothing_ser = persons["clothing_description"].fillna("").astype(str).str[:40] if "clothing_description" in persons.columns else pd.Series("", index=persons.index)
    height_col = "estimated_height_cm" if "estimated_height_cm" in persons.columns else "value"
    height_ser = persons[height_col].fillna(0).astype(int).astype(str) if height_col in persons.columns else pd.Series("0", index=persons.index)
    persons["identity_key"] = clothing_ser + "|" + height_ser
    agg_dict = {"visit_count": ("identity_key", "count"), "last_seen": (ts_col, "max")}
    if "clothing_description" in persons.columns:
        agg_dict["clothing"] = ("clothing_description", "first")
    if "estimated_height_cm" in persons.columns:
        agg_dict["height_cm"] = ("estimated_height_cm", "median")
    elif "value" in persons.columns:
        agg_dict["height_cm"] = ("value", "median")
    agg = persons.groupby("identity_key").agg(**agg_dict).reset_index()
    if "clothing" not in agg.columns:
        agg["clothing"] = agg["identity_key"].str.split("|").str[0]
    if "height_cm" not in agg.columns:
        agg["height_cm"] = 0
    agg["last_seen"] = agg["last_seen"].dt.strftime("%Y-%m-%d %H:%M")
    return agg.sort_values("visit_count", ascending=False).head(100)


def persons_table(df: pd.DataFrame) -> html.Div:
    """Aggregate person-like rows by clothing + height proxy; visit count, last seen."""
    agg = _persons_agg_df(df)
    if agg is None or agg.empty:
        return html.Div("No person data.", className="text-muted p-3")
    return html.Div(
        [
            html.P("Unique individuals (proxy by clothing + height; ReID stub for persistent IDs).", className="small text-muted mb-2"),
            dash_table.DataTable(
                data=agg.to_dict("records"),
                columns=[
                    {"name": "Visit count", "id": "visit_count"},
                    {"name": "Last seen", "id": "last_seen"},
                    {"name": "Clothing", "id": "clothing"},
                    {"name": "Height (cm)", "id": "height_cm"},
                ],
                id="persons-table",
                page_size=15,
                style_cell={"textAlign": "left", "padding": "8px"},
                style_header={"fontWeight": "bold"},
            ),
        ],
        className="overflow-auto",
    )


def layout() -> html.Div:
    return html.Div(
        [
            html.H5("Persons & tracks", className="mb-3"),
            dbc.Card(
                [
                    dbc.CardHeader(
                        [
                            html.I(className="bi bi-person-badge me-2"),
                            "Unique individuals",
                            dbc.Button(
                                [html.I(className="bi bi-download me-1"), "Export CSV"],
                                id="persons-export-csv",
                                size="sm",
                                outline=True,
                                color="primary",
                                className="ms-auto",
                            ),
                        ],
                        className="d-flex align-items-center flex-wrap",
                    ),
                    dbc.CardBody(html.Div(id="persons-container")),
                ],
                className="shadow-sm",
            ),
        ]
    )
