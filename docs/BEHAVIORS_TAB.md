# Behaviors Tab — Competitor-Aligned Features

The **Behaviors** tab is a single hub for rules, events, and tracking, aligned with enterprise VMS behavior and event management (e.g. Milestone rules/events, Genetec analytics, BriefCam-style activity views).

---

## Competitor Reference (Research Summary)

- **Rules and events**: Triggers (motion, loitering, line crossing) that generate alerts and optional actions (record, notify). Central place to see what is configured and what is firing.
- **Event feed with filtering**: Filter by event type, severity, date range, and (where applicable) camera. Saved filters and quick filters are common.
- **Activity over time**: Event density by time (e.g. by hour) for pattern review and “peak activity” visibility (heatmap-style or bar chart).
- **Summary cards**: Counts by behavior type (motion, loitering, line cross), unacknowledged count, and links to full event list.
- **Quick navigation**: Links to Events (full list), Timeline (history), Activity log (detection log), Analytics (aggregates), Map.

---

## What the Behaviors Tab Provides

| Feature | Description |
|--------|-------------|
| **Summary cards** | Counts for Motion, Loitering, Line crossing in the selected date range; “Needs review” count (unacknowledged) with link to Events. |
| **Active triggers** | Short list of what generates alerts: motion detection, loitering (dwell in zone), line crossing. Link to Settings to configure zones/lines. |
| **Activity today (by hour)** | Bar chart of event density per hour for today (from analytics aggregates). Helps spot peak activity. |
| **Event feed** | Filterable list (date range: Today / Last 7 days; behavior type; severity). Compact rows with timestamp, severity, behavior, camera, object; Ack button for unacknowledged. Sorted newest first, capped for performance. |
| **Quick links** | Events (full list), Timeline, Activity log, Analytics, Map. |

---

## Route and Navigation

- **Route**: `/behaviors`
- **Nav label**: “Behaviors”
- **Placement**: After “Events” in the main nav (Dashboard, Live, Events, **Behaviors**, Timeline, Log, Map, Analytics, Export, Settings).

---

## Future Enhancements (Optional)

- Saved filter presets (e.g. “Unack only”, “Loitering today”).
- Heatmap over a calendar or time grid (event density by day/hour).
- Per-camera breakdown in summary or feed.
- “Tracking” view: event sequences grouped by camera or time window for thread-style review.
