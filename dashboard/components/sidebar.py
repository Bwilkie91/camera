"""
Sidebar navigation: Overview, Timeline, Persons & Tracks, Alerts, Settings.
Enterprise: clear labels, icons via Bootstrap, active state.
"""
from dash import html
import dash_bootstrap_components as dbc

NAV_LINKS = [
    {"path": "/", "label": "Overview", "icon": "speedometer2"},
    {"path": "/live", "label": "Live", "icon": "camera-video"},
    {"path": "/timeline", "label": "Timeline", "icon": "clock-history"},
    {"path": "/persons", "label": "Persons & Tracks", "icon": "person-badge"},
    {"path": "/alerts", "label": "Alerts & Anomalies", "icon": "exclamation-triangle"},
    {"path": "/map", "label": "Map", "icon": "geo-alt"},
    {"path": "/settings", "label": "Settings", "icon": "gear"},
]


def sidebar(pathname: str = "/") -> html.Div:
    active = pathname or "/"
    items = []
    for link in NAV_LINKS:
        is_active = (link["path"] == "/" and active == "/") or (link["path"] != "/" and active.startswith(link["path"]))
        items.append(
            dbc.NavItem(
                dbc.NavLink(
                    [html.I(className=f"bi bi-{link['icon']} me-2"), link["label"]],
                    href=link["path"],
                    active=is_active,
                    style={"borderRadius": "0.375rem"},
                )
            )
        )
    return html.Div(
        [
            html.Div(
                [html.Span("Vigil", className="fw-bold"), html.Span(" SOC", style={"color": "var(--vigil-muted, #64748b)"})],
                className="fs-5 px-3",
            ),
            dbc.Nav(items, vertical=True, pills=True, className="flex-column px-2"),
        ],
        className="d-flex flex-column py-3",
        style={"minHeight": "100vh"},
    )
