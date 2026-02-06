"""
Enterprise Surveillance Dashboard — SOC-style (Verkada/Rhombus/Avigilon 2026).

Multi-page: Overview, Timeline, Persons & Tracks, Alerts, Settings.
Dark/light theme, global filters, polling, Plotly charts, detail modal, export.

Run from project root: python -m dashboard.app   or   python dashboard/app.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure project root on path for dashboard.* imports
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc

# Bootstrap theme: CYBORG (dark) for SOC; switchable to FLATLY (light)
THEME = "CYBORG"
app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.CYBORG,
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css",
    ],
    suppress_callback_exceptions=True,
    title="Vigil Command",
)

# Server for gunicorn/deploy
server = app.server

# ---- Load config ----
def _config():
    cfg_path = Path(__file__).resolve().parent / "config.yaml"
    if not cfg_path.is_file():
        return {}
    try:
        import yaml
        with open(cfg_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        return {}


CONFIG = _config()
POLL_INTERVAL = CONFIG.get("polling", {}).get("interval_ms", 30000)
THEME_DEFAULT = CONFIG.get("theme", {}).get("default", "dark")


def _initial_layout_components():
    """Build sidebar, header, filters, modal so their IDs exist in the initial layout."""
    from dashboard.components.sidebar import sidebar
    from dashboard.components.header import header
    from dashboard.components.filters import filters_card
    from dashboard.components.detail_modal import detail_modal
    return sidebar("/"), header(THEME_DEFAULT), filters_card(), detail_modal()


_initial_sidebar, _initial_header, _initial_filters, _initial_modal = _initial_layout_components()


def _all_pages_content():
    """Build all page layouts so every callback Output id exists in the initial layout."""
    from dashboard.pages.overview import layout as overview_layout
    from dashboard.pages.live import layout as live_layout
    from dashboard.pages.timeline import layout as timeline_layout
    from dashboard.pages.persons import layout as persons_layout
    from dashboard.pages.alerts import layout as alerts_layout
    from dashboard.pages.map import layout as map_layout
    from dashboard.pages.settings import layout as settings_layout
    return [
        html.Div(id="page-overview", children=overview_layout(), style={"display": "block"}),
        html.Div(id="page-live", children=live_layout(), style={"display": "none"}),
        html.Div(id="page-timeline", children=timeline_layout(), style={"display": "none"}),
        html.Div(id="page-persons", children=persons_layout(), style={"display": "none"}),
        html.Div(id="page-alerts", children=alerts_layout(), style={"display": "none"}),
        html.Div(id="page-map", children=map_layout(), style={"display": "none"}),
        html.Div(id="page-settings", children=settings_layout(), style={"display": "none"}),
    ]


_initial_page_content = _all_pages_content()

# ---- Layout: sidebar + header + main (include components so callback IDs exist) ----
# Skip link for WCAG 2.4.1 (bypass blocks); visible on focus
_skip_link_style = {
    "position": "absolute", "left": "-9999px", "padding": "0.5rem 1rem",
    "background": "var(--vigil-primary, #2563eb)", "color": "#fff", "fontWeight": "600",
    "zIndex": "9999", "borderRadius": "0.375rem",
}
app.layout = html.Div(
    [
        html.A("Skip to main content", href="#main-content", id="skip-link", style=_skip_link_style),
        dcc.Location(id="url", refresh=False),
        dcc.Store(id="theme-store", data=THEME_DEFAULT),
        dcc.Store(id="filtered-data-store", data=None),
        dcc.Store(id="raw-data-store", data=None),
        dcc.Interval(id="poll-interval", interval=POLL_INTERVAL, n_intervals=0),
        dcc.Download(id="timeline-download"),
        dcc.Download(id="persons-download"),
        dcc.Download(id="overview-download"),
        dcc.Download(id="alerts-download"),
        dbc.Container(
            [
                dbc.Row(
                    [
                        dbc.Col(
                            html.Div(id="sidebar-container", children=_initial_sidebar),
                            className="p-0",
                            style={"width": "220px", "minWidth": "220px", "flex": "0 0 220px"},
                        ),
                        dbc.Col(
                            [
                                html.Div(id="header-container", children=_initial_header),
                                dbc.Row(
                                    [
                                        dbc.Col(html.Div(id="filters-container", children=_initial_filters), width=2, className="pe-2 pt-3", style={"maxWidth": "200px"}),
                                        dbc.Col(html.Div(id="page-content", children=_initial_page_content), width=10, className="pt-3"),
                                    ],
                                    className="g-0 mx-0",
                                ),
                            ],
                            id="main-content",
                            className="flex-grow-1 min-vw-0 p-0",
                        ),
                    ],
                    className="g-0 flex-nowrap",
                    style={"minHeight": "100vh"},
                ),
            ],
            fluid=True,
            className="p-0",
        ),
        html.Div(id="detail-modal-container", children=_initial_modal),
    ],
    id="app-container",
    style={"minHeight": "100vh"},
)


# ---- Data load + filter ----
def _load_raw():
    from dashboard.utils.data_loader import load_data
    df = load_data(CONFIG)
    return df.to_dict("records") if df is not None and not df.empty else []


def _apply_filters(records, date_from, date_to, scene, obj, event, threat_min, clothing, value_min):
    from dashboard.utils.data_loader import apply_filters
    import pandas as pd
    if not records:
        return []
    df = pd.DataFrame(records)
    df = apply_filters(
        df,
        date_from=date_from,
        date_to=date_to,
        scene=scene or None,
        object_type=obj or None,
        event_type=event or None,
        threat_min=float(threat_min) if threat_min is not None and str(threat_min).strip() else None,
        clothing_search=clothing or None,
        value_min=float(value_min) if value_min is not None and str(value_min).strip() else None,
    )
    return df.to_dict("records")


# ---- Callbacks ----
@app.callback(
    [Output("sidebar-container", "children"), Output("header-container", "children"), Output("filters-container", "children"), Output("detail-modal-container", "children")],
    Input("theme-store", "data"),
    Input("url", "pathname"),
)
def render_layout(theme, pathname):
    from dashboard.components.sidebar import sidebar
    from dashboard.components.header import header
    from dashboard.components.filters import filters_card
    from dashboard.components.detail_modal import detail_modal
    theme = theme or "dark"
    return sidebar(pathname), header(theme), filters_card(), detail_modal()


# Show/hide page divs based on pathname (all pages stay in DOM so callback IDs exist)
@app.callback(
    [
        Output("page-overview", "style"),
        Output("page-live", "style"),
        Output("page-timeline", "style"),
        Output("page-persons", "style"),
        Output("page-alerts", "style"),
        Output("page-map", "style"),
        Output("page-settings", "style"),
    ],
    Input("url", "pathname"),
)
def render_page(pathname):
    pathname = pathname or "/"
    show = {"display": "block"}
    hide = {"display": "none"}
    return (
        show if pathname == "/" else hide,
        show if pathname == "/live" else hide,
        show if pathname == "/timeline" else hide,
        show if pathname == "/persons" else hide,
        show if pathname == "/alerts" else hide,
        show if pathname == "/map" else hide,
        show if pathname == "/settings" else hide,
    )




# Reload data on interval or when user clicks Refresh
@app.callback(
    [Output("raw-data-store", "data"), Output("header-last-updated", "children")],
    Input("poll-interval", "n_intervals"),
    Input("refresh-btn", "n_clicks"),
    prevent_initial_call=False,
)
def poll_data(n, _refresh_clicks):
    from datetime import datetime
    records = _load_raw()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return records, f"Updated {now}"


@app.callback(
    Output("filtered-data-store", "data"),
    Input("raw-data-store", "data"),
    Input("filter-apply", "n_clicks"),
    State("filter-date-from", "date"),
    State("filter-date-to", "date"),
    State("filter-scene", "value"),
    State("filter-object", "value"),
    State("filter-event", "value"),
    State("filter-threat-min", "value"),
    State("filter-clothing", "value"),
    State("filter-value-min", "value"),
)
def filter_data(raw, _apply, date_from, date_to, scene, obj, event, threat_min, clothing, value_min):
    # Update whenever raw data loads (e.g. polling) or user clicks Apply
    if not raw:
        return []
    return _apply_filters(raw, date_from, date_to, scene, obj, event, threat_min, clothing, value_min)


# Theme toggle
@app.callback(
    Output("theme-store", "data"),
    Input("theme-toggle", "n_clicks"),
    State("theme-store", "data"),
)
def toggle_theme(n, current):
    if not n:
        return current or "dark"
    return "light" if (current or "dark") == "dark" else "dark"


# Global search: parse query and update filters (simplified — just store query for now)
@app.callback(
    Output("global-search", "value"),
    Input("global-search", "value"),
)
def search_value(v):
    return v or ""


# ---- Overview: System status (Vigil API, Flask/React-style) ----
@app.callback(
    Output("overview-system-status", "children"),
    Input("poll-interval", "n_intervals"),
    Input("url", "pathname"),
)
def overview_system_status(n, pathname):
    if pathname not in (None, "/"):
        return dash.no_update
    from dashboard.utils.data_loader import fetch_system_status
    from dashboard.pages.overview import system_status_cards
    status = fetch_system_status(CONFIG)
    return system_status_cards(status)


# ---- Overview: KPIs + heatmap + occupancy ----
@app.callback(
    [Output("overview-kpis", "children"), Output("overview-heatmap", "figure"), Output("overview-occupancy", "figure")],
    Input("filtered-data-store", "data"),
    Input("url", "pathname"),
)
def overview_update(data, pathname):
    if pathname not in (None, "/"):
        return dash.no_update, dash.no_update, dash.no_update
    import pandas as pd
    from dashboard.pages.overview import kpi_cards, heatmap_figure, occupancy_figure
    df = pd.DataFrame(data) if data else pd.DataFrame()
    kpis = kpi_cards(df)
    heatmap = heatmap_figure(df)
    occ = occupancy_figure(df)
    return kpis, heatmap, occ


# ---- Overview: export filtered data as CSV ----
@app.callback(
    Output("overview-download", "data"),
    Input("overview-export-csv", "n_clicks"),
    State("filtered-data-store", "data"),
    prevent_initial_call=True,
)
def overview_export_csv(n_clicks, data):
    if not n_clicks or not data:
        return dash.no_update
    import pandas as pd
    df = pd.DataFrame(data)
    if df.empty:
        return dash.no_update
    return dcc.send_data_frame(df.to_csv, "overview_export.csv", index=False)


# ---- Live: grid preset store ----
@app.callback(
    Output("live-grid-preset", "data"),
    Input("live-grid-1", "n_clicks"),
    Input("live-grid-2", "n_clicks"),
    Input("live-grid-3", "n_clicks"),
    prevent_initial_call=True,
)
def live_grid_preset(_1, _2, _3):
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update
    tid = ctx.triggered[0]["prop_id"].split(".")[0]
    if tid == "live-grid-1":
        return "1"
    if tid == "live-grid-2":
        return "2"
    return "3"


# ---- Live: stream grid from Vigil API (Flask/React-style); grid presets 1×1, 2×2, 3×3 ----
@app.callback(
    Output("live-streams-container", "children"),
    Input("poll-interval", "n_intervals"),
    Input("url", "pathname"),
    Input("live-grid-preset", "data"),
    Input("live-refresh-btn", "n_clicks"),
)
def live_streams(n, pathname, grid_preset, _refresh_clicks):
    if pathname != "/live":
        return dash.no_update
    from dashboard.utils.data_loader import fetch_streams, get_api_base
    base = get_api_base(CONFIG)
    if not base:
        return html.Div(
            "Live streams require data.source: 'api' in config.yaml and data.api_base_url (e.g. http://localhost:5000). Restart the SOC app after changing config.",
            className="text-muted small",
        )
    streams = fetch_streams(CONFIG)
    if not streams:
        return html.Div(
            [
                html.P("No streams from Vigil. Check:", className="mb-1"),
                html.Ul(
                    [
                        html.Li("Vigil Flask is running on " + base),
                        html.Li("At least one camera is configured (e.g. CAMERA_SOURCES=0 in .env) and opened"),
                    ],
                    className="small text-muted mb-0",
                ),
            ]
        )
    import dash_bootstrap_components as dbc
    cols = {"1": 12, "2": 6, "3": 4}
    col_md = cols.get(str(grid_preset), 4)
    children = []
    for s in streams:
        url = s.get("url") or ""
        if url.startswith("/"):
            url = base + url
        else:
            url = base + "/" + url.lstrip("/")
        name = s.get("name") or s.get("camera_id") or "Stream"
        children.append(
            dbc.Card(
                [
                    dbc.CardHeader(
                        [html.Span("LIVE", className="badge bg-danger me-2"), name],
                        className="py-2",
                    ),
                    dbc.CardBody(html.Img(src=url, style={"width": "100%", "maxHeight": "320px", "objectFit": "contain", "background": "#111"})),
                ],
                className="mb-3 shadow-sm",
                style={"maxWidth": "480px"} if col_md >= 6 else None,
            )
        )
    return dbc.Row([dbc.Col(c, md=col_md, lg=col_md) for c in children], className="g-3")


# ---- Map: sites and camera positions from Vigil API ----
@app.callback(
    Output("map-site-select", "options"),
    Input("url", "pathname"),
)
def map_site_options(pathname):
    if pathname != "/map":
        return dash.no_update
    from dashboard.utils.data_loader import fetch_sites
    sites = fetch_sites(CONFIG)
    if not sites:
        return [{"label": "No sites (set data.source: api)", "value": ""}]
    return [{"label": s.get("name", s.get("id", "?")), "value": s.get("id", "")} for s in sites]


@app.callback(
    Output("map-content", "children"),
    Input("map-site-select", "value"),
    Input("url", "pathname"),
    Input("map-refresh-btn", "n_clicks"),
)
def map_content(site_id, pathname, _refresh_clicks):
    if pathname != "/map":
        return dash.no_update
    from dashboard.utils.data_loader import fetch_sites, fetch_camera_positions
    import dash_bootstrap_components as dbc
    sites = fetch_sites(CONFIG)
    if not sites:
        return html.Div("No data. Set data.source to 'api' in config.yaml.", className="text-muted small")
    if not site_id:
        return html.Div(html.P("Select a site above.", className="text-muted small"))
    site = next((s for s in sites if s.get("id") == site_id), None)
    if not site:
        return html.Div(html.P("Site not found.", className="text-muted small"))
    site_id = site.get("id")
    positions = fetch_camera_positions(CONFIG, site_id)
    map_url = site.get("map_url")
    rows = []
    if map_url:
        rows.append(dbc.Card([dbc.CardBody(html.Img(src=map_url, style={"maxWidth": "100%", "height": "auto"}))], className="mb-3"))
    rows.append(html.H6("Cameras", className="mt-2"))
    if positions:
        rows.append(html.Ul([html.Li(f"{p.get('label') or p.get('camera_id')} — ({p.get('x')}, {p.get('y')})") for p in positions], className="small"))
    else:
        rows.append(html.P("No camera positions for this site.", className="text-muted small"))
    return html.Div(rows)


# ---- Persons export ----
@app.callback(
    Output("persons-download", "data"),
    Input("persons-export-csv", "n_clicks"),
    State("filtered-data-store", "data"),
    prevent_initial_call=True,
)
def persons_export_csv(n_clicks, data):
    if not n_clicks or not data:
        return dash.no_update
    import pandas as pd
    from dashboard.pages.persons import _persons_agg_df
    df = _persons_agg_df(pd.DataFrame(data))
    if df is None or df.empty:
        return dash.no_update
    return dcc.send_data_frame(df.to_csv, "persons_export.csv", index=False)


# ---- Timeline: table ----
@app.callback(
    Output("timeline-table-container", "children"),
    Input("filtered-data-store", "data"),
    Input("url", "pathname"),
)
def timeline_update(data, pathname):
    if pathname != "/timeline":
        return dash.no_update
    import pandas as pd
    from dashboard.pages.timeline import event_table
    df = pd.DataFrame(data) if data else pd.DataFrame()
    return event_table(df)


# ---- Persons ----
@app.callback(
    Output("persons-container", "children"),
    Input("filtered-data-store", "data"),
    Input("url", "pathname"),
)
def persons_update(data, pathname):
    if pathname != "/persons":
        return dash.no_update
    import pandas as pd
    from dashboard.pages.persons import persons_table
    df = pd.DataFrame(data) if data else pd.DataFrame()
    return persons_table(df)


# ---- Alerts: threat dist + scatter + high list ----
@app.callback(
    [Output("alerts-threat-dist", "figure"), Output("alerts-anomaly-scatter", "figure"), Output("alerts-high-list", "children")],
    Input("filtered-data-store", "data"),
    Input("url", "pathname"),
)
def alerts_update(data, pathname):
    if pathname != "/alerts":
        return dash.no_update, dash.no_update, dash.no_update
    import pandas as pd
    from dashboard.pages.alerts import threat_distribution_figure, anomaly_scatter_figure
    from dashboard.utils.data_loader import get_vigil_ui_base
    from urllib.parse import urlencode
    df = pd.DataFrame(data) if data else pd.DataFrame()
    threat_fig = threat_distribution_figure(df)
    scatter_fig = anomaly_scatter_figure(df)
    vigil_base = get_vigil_ui_base(CONFIG)
    # High-threat list with "Play at moment" link
    if not df.empty and "threat_score" in df.columns:
        high = df[pd.to_numeric(df["threat_score"], errors="coerce").fillna(0) > 0]
        ev = df.get("event")
        loiter = df[ev.astype(str).str.lower().str.contains("loitering", na=False)] if ev is not None else pd.DataFrame()
        combined = pd.concat([high, loiter]).drop_duplicates().head(20)
        ts_col = "timestamp_local" if "timestamp_local" in combined.columns else "local_timestamp"
        if ts_col not in combined.columns:
            ts_col = "timestamp_utc"
        if not combined.empty and ts_col in combined.columns:
            combined[ts_col] = pd.to_datetime(combined[ts_col], errors="coerce")
            list_items = []
            for _, row in combined.iterrows():
                ts_val = row.get(ts_col)
                ts_iso = None
                if ts_val is not None and pd.notna(ts_val) and hasattr(ts_val, "isoformat"):
                    try:
                        ts_iso = ts_val.isoformat().replace(" ", "T")[:23]
                    except Exception:
                        pass
                cam = row.get("camera_id")
                line = html.Span(f"{ts_val} — {row.get('event', '')} — threat {row.get('threat_score', 0)}", className="small")
                if vigil_base and ts_iso:
                    qs = urlencode({"playback_ts": ts_iso, **({"playback_camera_id": str(cam)} if cam is not None and str(cam).strip() else {})})
                    play_link = html.A(
                        [html.I(className="bi bi-play-circle me-1"), "Play"],
                        href=f"{vigil_base.rstrip('/')}/activity?{qs}",
                        target="_blank",
                        rel="noopener noreferrer",
                        className="btn btn-sm btn-outline-primary ms-2",
                    )
                    list_items.append(html.Li([line, play_link], className="small d-flex align-items-center flex-wrap mb-1"))
                else:
                    list_items.append(html.Li(line, className="small"))
        else:
            list_items = [html.Li("No high-threat or loitering events", className="text-muted small")]
    else:
        list_items = [html.Li("No data", className="text-muted small")]
    high_list = html.Ul(list_items, className="list-unstyled mb-0")
    return threat_fig, scatter_fig, high_list


# ---- Alerts: export high-threat & loitering as CSV ----
@app.callback(
    Output("alerts-download", "data"),
    Input("alerts-export-csv", "n_clicks"),
    State("filtered-data-store", "data"),
    prevent_initial_call=True,
)
def alerts_export_csv(n_clicks, data):
    if not n_clicks or not data:
        return dash.no_update
    import pandas as pd
    df = pd.DataFrame(data)
    if df.empty or "threat_score" not in df.columns:
        return dash.no_update
    high = df[pd.to_numeric(df["threat_score"], errors="coerce").fillna(0) > 0]
    ev = df.get("event")
    loiter = df[ev.astype(str).str.lower().str.contains("loitering", na=False)] if ev is not None else pd.DataFrame()
    combined = pd.concat([high, loiter]).drop_duplicates()
    if combined.empty:
        return dash.no_update
    return dcc.send_data_frame(combined.to_csv, "alerts_high_threat_loitering.csv", index=False)


# ---- Detail modal: open on timeline row select ----
@app.callback(
    [Output("detail-modal", "is_open"), Output("detail-modal-body", "children")],
    Input("timeline-table", "selected_row_ids"),
    Input("detail-modal-close", "n_clicks"),
    State("detail-modal", "is_open"),
    State("filtered-data-store", "data"),
    prevent_initial_call=True,
)
def modal_toggle(selected_ids, close_click, is_open, data):
    from dashboard.components.detail_modal import build_modal_body
    from dashboard.utils.data_loader import get_vigil_ui_base
    if close_click:
        return False, []
    if selected_ids and data:
        import pandas as pd
        df = pd.DataFrame(data)
        try:
            idx = int(selected_ids[0])
            if 0 <= idx < len(df):
                row = df.iloc[idx].to_dict()
                vigil_base = get_vigil_ui_base(CONFIG)
                return True, build_modal_body(row, vigil_ui_base=vigil_base)
        except (ValueError, TypeError, IndexError):
            pass
    return is_open, dash.no_update


# ---- Export ----
@app.callback(
    Output("timeline-download", "data"),
    Input("timeline-export-csv", "n_clicks"),
    Input("timeline-export-json", "n_clicks"),
    State("filtered-data-store", "data"),
    prevent_initial_call=True,
)
def export_timeline(csv_click, json_click, data):
    if not data:
        return dash.no_update
    import pandas as pd
    df = pd.DataFrame(data)
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update
    tid = ctx.triggered[0]["prop_id"]
    if "export-csv" in tid:
        return dcc.send_data_frame(df.to_csv, "surveillance_export.csv", index=False)
    if "export-json" in tid:
        return dcc.send_string(json.dumps(df.to_dict("records"), default=str), "surveillance_export.json")
    return dash.no_update


if __name__ == "__main__":
    app.run(debug=True, port=8050)
