# Flask UI/UX Overhaul

This document describes the radical redesign of the Vigil Flask UI: fewer sections, clearer navigation, better data visuals, and easier export.

## Goals

- **Remove redundancy**: Combine related pages (Activity = Events + Timeline + Chart; Export = CSV + Recordings + Map + Analytics).
- **Improve color scheme and data visuals**: Dark theme with teal accent, severity badges, and activity chart with intensity-based bar colors.
- **Improve video playback**: Stream viewer with fullscreen support and clear controls.
- **Easier export**: Single Export section with AI data (CSV), recordings, map, and analytics in one place.

## Navigation

- **Live** — Camera streams, snapshot, recording/PTZ controls.
- **Activity** — Single section with tabs: **Events**, **Timeline**, **Chart** (replaces separate Events, Behaviors, Timeline, Log pages).
- **Export** — AI data (CSV), verify log, recordings list, **Map** (site/cameras), **Analytics** (date-range aggregates + Export CSV).
- **Settings** — App configuration (unchanged).

Help (?) and Sign in / Auto sign-in remain in the nav bar.

## Layout and Color Scheme

- **CSS variables** (in `templates/index.html`):
  - `--bg`, `--bg-elevated`, `--surface`, `--border`: Dark neutrals.
  - `--accent` / `--accent-hover`: Teal (#14b8a6) for primary actions and highlights.
  - `--high`, `--medium`, `--low`, `--ok`, `--warn`: Severity and status.
- **KPI grid**: Four cards (Recording, Events today, Needs review, Streams) linking to Live or Activity.
- **Sections**: Card-based; consistent `--radius`, `--shadow`, and borders.

## Live and Stream UX

- Each stream is in a **stream-viewer** container (16:9) with:
  - Live MJPEG image.
  - **Fullscreen** button (top-right); toggles to "Exit fullscreen" when active; ESC exits fullscreen.
  - Audio toggle, Take Snapshot, snapshots strip, Export data + snapshots, video downloads.
- Status & controls: System status, Recording & PTZ, AI Detection Log in one row below Live.

## Activity Section

- **Events** tab: Filters (type, severity, acknowledged), search, refresh; event list with Ack.
- **Timeline** tab: Range (24h, 7 days, All), refresh; time-ordered list with expand/collapse details.
- **Chart** tab: Counts (Motion, Loitering, Line cross, Needs review), **activity-by-hour bar chart** (intensity-based teal bars), filter by type, behavior feed list.
- Tab switching loads Timeline or Chart on demand; Events list shared where relevant.

## Export & Data

- **Export** section is streamlined:
  1. **Data export** row: **AI data (CSV)**, **Verify**, **AI log (.txt)**; recordings list below.
  2. **Map** subsection: Site select, map image, camera list.
  3. **Analytics** subsection: Date range, Load, **Aggregates (CSV)**; summary cards and table.
- One place for all downloads; short labels and no redundant copy. The AI Detection Log card in Status & controls no longer has its own export button—it links to Export to avoid duplicate actions. **Audit log (CSV)** and **Verify audit** are in the same Data export row (admin-only enforced by backend).

Map and Analytics are no longer separate top-level sections; they live under Export to reduce navigation and group all “data and export” in one place.

## Data Visuals

- **Activity chart**: 24-hour bar chart; bar height = events per hour; bar color = teal with opacity scaled by value (higher = more opaque) for quick scan.
- **Severity badges**: Consistent `badge-high`, `badge-medium`, `badge-low`, etc.
- **Status indicators**: Recording (blinking REC), mic on/off, system status with OK/Degraded/Error.

## Accessibility and JS

- ARIA: `role="tablist"`, `role="tab"`, `role="tabpanel"`, `aria-selected`, `aria-label` on fullscreen and filters.
- Fullscreen: `fullscreenchange` used to update button label and `aria-label`.
- Single set of event listeners for activity tabs and timeline range; no duplicate handlers.

## Files

- **Flask UI**: `templates/index.html` (structure, styles, and inline script for streams, activity tabs, timeline, behaviors chart, export, map, analytics).
- **Related**: `docs/UNIFIED_ACTIVITY_UX.md` (Activity merge rationale), `docs/FRONTEND_UI_AUDIT.md` (broader UI notes).

## Keyboard shortcuts

- **?** — Toggle help modal.
- **F** — Toggle fullscreen when focus is on a stream viewer. Stream viewers are focusable (`tabindex="0"`).

## Future Options

- Optional “compact mode” that hides Map/Analytics under a toggle.
- More chart types (e.g. by camera) in Activity → Chart.
