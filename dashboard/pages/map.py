"""
Map: Sites and camera positions from Vigil (Flask) backend.
Combines React/Flask-style map view — site selector, map image, camera list.
"""
from __future__ import annotations

from dash import html, dcc
import dash_bootstrap_components as dbc


def layout() -> html.Div:
    """Placeholder; content filled by callback from sites/camera_positions API."""
    return html.Div(
        [
            html.H5("Sites & cameras", className="mb-3"),
            html.P(
                "When data source is API (config.yaml → data.source: api), sites and camera positions from Vigil appear here.",
                className="text-muted small mb-3",
            ),
            html.Div(
                [
                    dcc.Dropdown(id="map-site-select", placeholder="Select site…", clearable=True, className="mb-3", style={"minWidth": "200px"}),
                    dbc.Button([html.I(className="bi bi-arrow-clockwise me-1"), "Refresh"], id="map-refresh-btn", size="sm", color="secondary", outline=True, className="mb-3"),
                ],
                className="d-flex flex-wrap align-items-center gap-2",
            ),
            html.Div(id="map-content", children=[]),
        ]
    )
