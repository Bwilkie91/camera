"""
Live: MJPEG streams from Vigil (Flask) backend.
Grid presets (1×1, 2×2, 3×3), fullscreen per tile (F key). 2026 standards: FPS/latency in UI.
"""
from __future__ import annotations

from dash import html, dcc
import dash_bootstrap_components as dbc


def layout() -> html.Div:
    """Live stream grid; preset controls and container filled by callback."""
    return html.Div(
        [
            html.H5("Live streams", className="mb-3"),
            html.P(
                "When data source is API (config.yaml → data.source: api), streams from the Vigil backend appear here. Focus a stream and press F for fullscreen.",
                className="text-muted small mb-3",
            ),
            html.Div(
                [
                    html.Span("Grid layout:", className="me-2 text-muted small"),
                    dbc.ButtonGroup(
                        [
                            dbc.Button("1×1", id="live-grid-1", size="sm", color="secondary", outline=True),
                            dbc.Button("2×2", id="live-grid-2", size="sm", color="secondary", outline=True),
                            dbc.Button("3×3", id="live-grid-3", size="sm", color="secondary", outline=True),
                        ],
                        className="me-3",
                    ),
                    dbc.Button([html.I(className="bi bi-arrow-clockwise me-1"), "Refresh"], id="live-refresh-btn", size="sm", color="secondary", outline=True, title="Reload stream list"),
                ],
                className="mb-2 d-flex flex-wrap align-items-center gap-2",
            ),
            dcc.Store(id="live-grid-preset", data="3"),
            html.Div(id="live-streams-container", children=[]),
        ]
    )
