"""
Theme and styling: dark/light, accent colors, chart templates.
Enterprise: consistent CYBORG/FLATLY, threat red, anomaly orange.
"""
from __future__ import annotations

from typing import Any

# Defaults (overridden by config)
DARK_THEME = "CYBORG"
LIGHT_THEME = "FLATLY"
ACCENT_THREAT = "#dc3545"
ACCENT_ANOMALY = "#fd7e14"
ACCENT_OK = "#20c997"

# Plotly layout template for dark mode (reduces glare in SOC)
PLOTLY_DARK = {
    "layout": {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": "#adb5bd", "family": "Inter, system-ui, sans-serif"},
        "xaxis": {"gridcolor": "rgba(255,255,255,0.08)", "zerolinecolor": "rgba(255,255,255,0.1)"},
        "yaxis": {"gridcolor": "rgba(255,255,255,0.08)", "zerolinecolor": "rgba(255,255,255,0.1)"},
        "colorway": ["#0d6efd", ACCENT_THREAT, ACCENT_ANOMALY, ACCENT_OK, "#6f42c1", "#0dcaf0"],
        "margin": {"t": 40, "r": 20, "b": 40, "l": 60},
        "hovermode": "x unified",
    }
}

PLOTLY_LIGHT = {
    "layout": {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": "#212529", "family": "Inter, system-ui, sans-serif"},
        "xaxis": {"gridcolor": "rgba(0,0,0,0.08)", "zerolinecolor": "rgba(0,0,0,0.1)"},
        "yaxis": {"gridcolor": "rgba(0,0,0,0.08)", "zerolinecolor": "rgba(0,0,0,0.1)"},
        "colorway": ["#0d6efd", ACCENT_THREAT, ACCENT_ANOMALY, ACCENT_OK, "#6f42c1", "#0dcaf0"],
        "margin": {"t": 40, "r": 20, "b": 40, "l": 60},
        "hovermode": "x unified",
    }
}


def get_theme_constants(config: dict[str, Any] | None) -> dict[str, str]:
    """Return theme name and bootstrap theme string from config."""
    t = (config or {}).get("theme", {})
    return {
        "dark_theme": t.get("dark_theme", DARK_THEME),
        "light_theme": t.get("light_theme", LIGHT_THEME),
        "default": t.get("default", "dark"),
        "accent_threat": t.get("accent_threat", ACCENT_THREAT),
        "accent_anomaly": t.get("accent_anomaly", ACCENT_ANOMALY),
        "accent_ok": t.get("accent_ok", ACCENT_OK),
    }
