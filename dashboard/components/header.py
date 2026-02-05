"""
Header: theme toggle, global search, last-updated.
Enterprise: compact, accessible, no clutter.
"""
from dash import dcc, html
import dash_bootstrap_components as dbc


def header(theme: str = "dark") -> html.Div:
    return dbc.Navbar(
        dbc.Container(
            [
                dbc.NavbarBrand("Surveillance Command", className="fw-semibold"),
                dbc.Row(
                    [
                        dbc.Col(
                            dcc.Input(
                                id="global-search",
                                type="text",
                                placeholder='Search e.g. "loitering at night gray clothing"',
                                className="form-control form-control-sm",
                                style={"minWidth": "260px", "maxWidth": "320px"},
                                debounce=True,
                            ),
                            width="auto",
                            className="me-3",
                        ),
                        dbc.Col(
                            html.Div(id="header-last-updated", className="small", style={"color": "var(--vigil-text-muted, #94a3b8)"}),
                            width="auto",
                            className="me-3 align-self-center",
                        ),
                        dbc.Col(
                            dbc.Button(
                                [html.I(className="bi bi-arrow-clockwise me-1"), "Refresh"],
                                id="refresh-btn",
                                color="secondary",
                                size="sm",
                                outline=True,
                                className="me-2 border-secondary text-secondary",
                                title="Reload data now",
                            ),
                            width="auto",
                        ),
                        dbc.Col(
                            dbc.Button(
                                [html.I(className="bi bi-moon-fill me-1"), "Dark"] if theme == "light" else [html.I(className="bi bi-sun-fill me-1"), "Light"],
                                id="theme-toggle",
                                color="secondary",
                                size="sm",
                                outline=True,
                                className="border-secondary text-secondary",
                            ),
                            width="auto",
                        ),
                    ],
                    className="g-2 align-items-center",
                ),
            ],
            fluid=True,
            className="d-flex justify-content-between align-items-center",
        ),
        color="dark" if theme == "dark" else "light",
        dark=(theme == "dark"),
        className="vigil-header shadow-sm",
    )
