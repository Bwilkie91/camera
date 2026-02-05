"""
Global filters: date range, scene, object, event, threat/anomaly, clothing.
Stored in dcc.Store; applied in callbacks before rendering charts.
"""
from dash import dcc, html
import dash_bootstrap_components as dbc


def filters_card() -> html.Div:
    return dbc.Card(
        [
            dbc.CardHeader([html.I(className="bi bi-funnel me-2"), "Filters"], className="py-2 small text-uppercase"),
            dbc.CardBody(
                [
                    dbc.Row(
                        [
                            dbc.Label("Date from", className="small"),
                            dcc.DatePickerSingle(
                                id="filter-date-from",
                                placeholder="Start",
                                clearable=True,
                                className="dash-datepicker",
                            ),
                        ],
                        className="mb-2",
                    ),
                    dbc.Row(
                        [
                            dbc.Label("Date to", className="small"),
                            dcc.DatePickerSingle(
                                id="filter-date-to",
                                placeholder="End",
                                clearable=True,
                            ),
                        ],
                        className="mb-2",
                    ),
                    dbc.Row(
                        [
                            dbc.Label("Scene", className="small"),
                            dcc.Dropdown(
                                id="filter-scene",
                                options=[{"label": "All", "value": ""}, {"label": "Indoor", "value": "Indoor"}, {"label": "Outdoor", "value": "Outdoor"}],
                                value="",
                                clearable=False,
                            ),
                        ],
                        className="mb-2",
                    ),
                    dbc.Row(
                        [
                            dbc.Label("Object", className="small"),
                            dcc.Dropdown(
                                id="filter-object",
                                options=[
                                    {"label": "All", "value": ""},
                                    {"label": "Person", "value": "person"},
                                    {"label": "Dog", "value": "dog"},
                                    {"label": "Cat", "value": "cat"},
                                    {"label": "Bottle", "value": "bottle"},
                                    {"label": "Cell phone", "value": "cell phone"},
                                ],
                                value="",
                                clearable=False,
                            ),
                        ],
                        className="mb-2",
                    ),
                    dbc.Row(
                        [
                            dbc.Label("Event", className="small"),
                            dcc.Dropdown(
                                id="filter-event",
                                options=[
                                    {"label": "All", "value": ""},
                                    {"label": "Motion", "value": "motion"},
                                    {"label": "Loitering", "value": "loitering"},
                                    {"label": "Line crossing", "value": "line_cross"},
                                    {"label": "Fall", "value": "fall"},
                                    {"label": "Crowding", "value": "crowding"},
                                ],
                                value="",
                                clearable=False,
                            ),
                        ],
                        className="mb-2",
                    ),
                    dbc.Row(
                        [
                            dbc.Label("Threat ≥", className="small"),
                            dbc.Input(id="filter-threat-min", type="number", min=0, max=100, step=5, value=None, placeholder="0"),
                        ],
                        className="mb-2",
                    ),
                    dbc.Row(
                        [
                            dbc.Label("Clothing", className="small"),
                            dbc.Input(id="filter-clothing", type="text", placeholder="e.g. gray"),
                        ],
                        className="mb-2",
                    ),
                    dbc.Row(
                        [
                            dbc.Label("Value ≥ (height/bbox)", className="small"),
                            dbc.Input(id="filter-value-min", type="number", min=0, max=300, step=5, value=None, placeholder="—"),
                        ],
                        className="mb-2",
                    ),
                    dbc.Button("Apply", id="filter-apply", color="primary", size="sm", className="w-100 mt-1"),
                ],
                className="py-2 px-3",
            ),
        ],
        className="shadow-sm",
    )
