# Missing UI Buttons — Scan

Single reference for **missing or suggested UI buttons/actions** across the app. Use this for prioritised UX/feature parity work.

---

## 1. Backend Exists, No UI Button

| Backend | Suggested location | Notes |
|---------|--------------------|--------|
| ~~**POST /toggle_motion**~~ | **Live** view | **Done.** Flask had it; React Live now has Motion on/off (toggleMotion API). No frontend call; no “Motion on/off” or “Enable motion” button. Add e.g. “Motion” toggle next to Record/PTZ. |
| **GET /api/v1/users** | **Settings** (admin) | List users. No “User management” or “Users” section. Admin cannot see or manage users in UI. |
| **GET /api/v1/users/<id>/sites**, **PUT /api/v1/users/<id>/sites** | **Settings** (admin) | Assign allowed sites to a user. No UI to view or edit per-user site access. |

---

## 2. Optional / Nice-to-Have Buttons

| Feature | Suggested location | Notes |
|---------|--------------------|--------|
| **Refresh system status** | **Dashboard** | Manual refresh for system status (e.g. “Refresh” next to status section). Data can refetch on interval; button improves perceived control. |
| ~~**Export aggregates (CSV)**~~ | **Analytics** | **Done.** React Analytics has "Aggregates (CSV)" button; Flask has "Aggregates (CSV)" in Export → Analytics. |
| **Full screen map** | **Map** | “Full screen” for map view (browser Fullscreen API). Minor. |
| **Timeline: export filtered events** | **Timeline** | Export current filtered event set as CSV (e.g. “Export events” when a range is selected). Could use existing events API + client-side CSV. |

---

## 3. Buttons That Exist (Quick Reference)

| View | Buttons |
|------|--------|
| **Export** | Export AI Data (CSV), Verify detection log, per recording: AVI, MP4, **View manifest**, Close (manifest panel) |
| **Settings** | Change password, MFA setup/confirm/cancel, Save (analytics config), Export audit log (CSV), **Verify audit log**, (audit table) |
| **Live** | Start/Stop Recording, PTZ Left/Right/Stop |
| **Dashboard** | Detect cameras |
| **Events** | Acknowledge (per event), Search |
| **Timeline** | Range (24h / 7d / All), Expand (per row) |
| **Login** | Sign in, Cancel (MFA), Back |
| **App** | ? (help), Logout |
| **ErrorBoundary** | Dismiss |

---

## 4. Recommended Order to Add

1. ~~**Live: Motion on/off**~~ — **Done** (React Live has Motion on/off).
2. **Settings (admin): User management** — List users + “Edit sites” per user using GET/PUT `/api/v1/users/<id>/sites`.
3. ~~**Dashboard: Refresh**~~ — **Done** — Optional “Refresh” for system status.
4. ~~**Analytics: Export aggregates**~~ — **Done** — Optional CSV download for current date range.
5. **Map: Full screen** — Optional.
6. ~~**Timeline: Export events**~~ — **Done** (Activity → Events tab has "Export events (CSV)").

---

## 5. API Client Gaps (if adding above)

- **Toggle motion**: Add `toggleMotion()` and optional `fetchMotionStatus()` if backend exposes status; wire to Live.
- **User management**: Add `fetchUsers()`, `fetchUserSites(userId)`, `updateUserSites(userId, siteIds)`; wire to Settings (admin-only section).
