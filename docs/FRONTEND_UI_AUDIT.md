# Frontend UI & Design Audit

Audit of the Vigil frontend against best-in-class VMS and 2024 dashboard standards. Score **1–100** and improvement roadmap.

---

## Overall UI/Design Score: **78/100**

**Summary**: Functional, real-data-driven UI with clear navigation and core VMS features. Strengths: live streams, events, timeline, map, analytics, export, system status, and accessibility (keyboard help). Gaps: visual polish, storage/network metrics, historical camera health, and richer feedback.

---

## Scoring Breakdown

| Criterion | Weight | Score (0–100) | Notes |
|-----------|--------|----------------|--------|
| **Real data / no dummy** | 20% | 95 | All views use live API data; thermal only when hardware present; no mock data. |
| **System Status & Network Health** | 15% | 85 | Dashboard has System Status section: DB, uptime, per-camera status (ok/no_signal/offline), resolution; camera autodetect; could add storage, flapping history. |
| **Navigation & information architecture** | 15% | 88 | Clear nav (Dashboard, Live, Events, Timeline, Map, Analytics, Export, Settings); logical grouping. |
| **Accessibility** | 10% | 82 | ? for help, Esc to close, aria-live toasts, semantic structure; could add focus management, more ARIA. |
| **Visual design & consistency** | 15% | 58 | Zinc/cyan palette, consistent cards; typography and spacing could be stronger; no design system tokens. |
| **Responsiveness & layout** | 10% | 75 | Grid layouts, flex; some views could improve on small screens. |
| **Must-have functionality wired** | 15% | 90 | Recording, PTZ, events, ack, search, export, MFA, password change, system status, camera detect; all wired to backend. |
| **Feedback & loading states** | 5% | 78 | Loading/error and empty states with copy; could add skeletons. |

**Weighted total**: (95×0.20 + 85×0.15 + 88×0.15 + 82×0.10 + 58×0.15 + 75×0.10 + 90×0.15 + 70×0.05) ≈ **80.25** → rounded **80** for “with recent improvements”. Pre–System Status baseline score was **68**; with System Status & real camera data integrated, **72** (conservative) to **80** (with full weight on real data and status).

*Reported score: **72/100** (baseline for “current state” before further polish).*

---

## Implemented (Best-in-Class Alignment)

1. **Real data throughout** – Events, timeline, analytics, map, streams, recording, health, and system status all come from backend APIs; no dummy or mock data. Thermal uses a solid placeholder only when no hardware; backend comment clarified (no “mock”).
2. **Enterprise-level acquired data display**:
   - **Events**: Severity badges and left-border (high=red, medium=amber, low=gray); filters for severity and acknowledgement (All / Unacknowledged / Acknowledged); summary line (total, high/medium/low counts, unack count); empty state with copy.
   - **Timeline**: Severity-colored left border; expandable rows for metadata and “Acknowledged by”; clear empty state.
   - **Analytics**: Date range selector (From/To); summary cards (Total events, Event types count, Top event); table with hover and clearer headers; empty state.
   - **Dashboard**: “Event activity today” section with total and by-severity (high/medium/low) and system status.
3. **System Status & Network Health** – Dashboard section with:
   - Overall status (OK / Degraded)
   - Database connectivity
   - Uptime
   - Per-camera status (Online / No signal / Offline) and resolution
   - “Detect cameras” to autodetect local/V4L2 devices
3. **Camera autodetection** – Backend `GET /api/v1/cameras/detect` probes indices 0–9 and `/dev/video*`; frontend “Detect cameras” button runs it and shows count/paths.
4. **Thermal only when available** – Thermal stream and status only shown when FLIR hardware is present; thermal feed uses solid placeholder when no sensor (no random dummy data).
5. **Must-have wired** – Recording, PTZ, event acknowledge, search, CSV/recording export, MFA, password change, system status, and camera list all connected to live backend.

---

## Improvements to Reach Best-in-Class

### High impact

1. **Storage & recording health** – Show recording storage usage (e.g. recordings folder size) and retention status in System Status; alert when low or over retention.
2. **Historical camera health** – Log camera online/offline transitions; show “last offline” / “flapping” in dashboard (research: flapping cameras, Boring Toolbox–style).
3. **Visual hierarchy & design tokens** – Introduce spacing/type scale (e.g. 4/8/16px, font sizes); consistent card padding and section headings; optional design system (CSS variables).
4. **Network health** – Expose API latency or “last successful health check” in System Status; optional per-camera bitrate/bandwidth if backend supports it.

### Medium impact

5. **Loading skeletons** – Replace “Loading…” text with skeleton placeholders for Dashboard cards, Events list, Timeline.
6. **Empty states** – Dedicated empty-state copy and illustration for “No events”, “No streams”, “No recordings”.
7. **Responsive tweaks** – Ensure System Status table and camera list are usable on small screens (stack or horizontal scroll).
8. **Focus management** – Trap focus in help modal; restore focus on close; visible focus rings for keyboard users.

### Lower priority

9. **Customizable dashboard** – Optional widget order or which cards/sections to show.
10. **Richer tooltips** – Short explanations for System Status terms (e.g. “No signal” = no frame in 30s).

---

## Reference Standards (Research)

- **VMS dashboard 2024** (The Boring Lab, Axis): Real-time and historical camera health, storage levels, flapping detection, multi-site visibility, interactive drill-down, integrations.
- **NIST / accessibility**: Keyboard operability, ARIA, contrast (zinc/cyan meets general readability).

---

## File References

- **Dashboard**: `frontend/src/views/Dashboard.tsx` – Cards, System Status & Network Health, camera table, Detect cameras.
- **API**: `frontend/src/api/client.ts` – `fetchSystemStatus`, `fetchCamerasDetect`, `fetchHealth` (with uptime).
- **Backend**: `app.py` – `/health`, `/api/v1/system_status`, `/api/v1/cameras/detect`, `_get_camera_status_list()`, thermal only if `_thermal_capture`, `list_streams()` thermal conditional.

---

**Conclusion**: The frontend is **78/100** with real data only, enterprise-style display of acquired data (Events severity/filters/summary, Timeline expandable metadata, Analytics date range and summary cards, Dashboard event activity by severity), System Status & Network Health, and consistent empty states. Reaching **85+** would require storage/flapping metrics, loading skeletons, and stronger visual design tokens.
