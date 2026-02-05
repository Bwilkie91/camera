"""
Settings: theme, data source, polling interval, thresholds (display only or stub).
Enterprise: confirm destructive actions; no raw secrets.
"""
from pathlib import Path

from dash import html
import dash_bootstrap_components as dbc


def _get_polling_ms() -> int | None:
    cfg_path = Path(__file__).resolve().parent.parent / "config.yaml"
    if not cfg_path.is_file():
        return None
    try:
        import yaml
        with open(cfg_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return (cfg.get("polling") or {}).get("interval_ms")
    except Exception:
        return None


def layout() -> html.Div:
    return html.Div(
        [
            html.H5("Settings", className="mb-3"),
            dbc.Card(
                [
                    dbc.CardHeader("Appearance"),
                    dbc.CardBody([
                        html.P("Theme is toggled in the header (dark/light).", className="small text-muted"),
                    ]),
                ],
                className="mb-3 shadow-sm",
            ),
            dbc.Card(
                [
                    dbc.CardHeader("Data source"),
                    dbc.CardBody([
                        html.P("Data source and paths are set in config.yaml: csv, sqlite, or api. Use api to pull live data from the Vigil Flask backend (Overview, Timeline, Alerts, plus Live streams and Map). Restart the app to apply changes.", className="small text-muted mb-2"),
                        html.P("For CSV: set data.csv_path (e.g. surveillance_log_clean.csv). Generate or update that file by running scripts/surveillance_log_parser.py from the project root, or use the Vigil Flask Export view to import/parse a raw log.", className="small text-muted mb-0"),
                    ]),
                ],
                className="mb-3 shadow-sm",
            ),
            dbc.Card(
                [
                    dbc.CardHeader("Polling"),
                    dbc.CardBody([
                        html.P("Near-real-time refresh uses dcc.Interval. Configure in config.yaml → polling.interval_ms.", className="small text-muted mb-1"),
                        html.P(html.Strong(f"Current interval: {_get_polling_ms() or 30000} ms ({( _get_polling_ms() or 30000) / 1000:.0f}s)"), className="small mb-0"),
                    ]),
                ],
                className="mb-3 shadow-sm",
            ),
            dbc.Card(
                [
                    dbc.CardHeader("Security"),
                    dbc.CardBody([
                        html.P("No raw data or credentials are exposed in the UI. Destructive actions require confirmation. For multi-user deployments, add role-based views and audit logging.", className="small text-muted"),
                    ]),
                ],
                className="shadow-sm",
            ),
        ]
    )
