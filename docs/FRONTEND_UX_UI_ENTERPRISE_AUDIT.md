# Frontend UX/UI Enterprise Audit — Highest Standards

Scan of **all Vigil frontends** (React, legacy HTML, Plotly Dash) against **enterprise-grade UX/UI standards**: WCAG 2.2 (Level A/AA), Nielsen’s 10 Usability Heuristics, and SOC/enterprise dashboard best practices. This doc identifies **missing or weak** areas and prioritizes remediation.

**Scope:** `frontend/` (React), `templates/` (legacy HTML), `dashboard/` (Plotly Dash).

**References (research):**
- [WCAG 2.2 Quick Reference](https://www.w3.org/WAI/WCAG22/quickref/) — Perceivable, Operable, Understandable, Robust.
- [Nielsen Norman Group: 10 Usability Heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/) and [Heuristic Evaluation](https://www.nngroup.com/articles/how-to-conduct-a-heuristic-evaluation/).
- [WebAIM WCAG 2 Checklist](https://webaim.org/standards/wcag/checklist).
- SOC/enterprise: Unified UI, severity-based prioritization, contextual visualization, reduced alert fatigue, widget-based flexibility (e.g. [SOAPA / SOC UX](https://www.msspalert.com/post/user-interface-experience-ui-ux)).

---

## 1. Audit framework summary

| Framework | Focus | Enterprise target |
|-----------|--------|-------------------|
| **WCAG 2.2 Level A** | Must-haves (alt, keyboard, structure) | 100% for legal/accessibility compliance |
| **WCAG 2.2 Level AA** | Contrast 4.5:1, captions, focus, reflow | 100% for public/enterprise |
| **Nielsen 1–10** | Visibility of status, consistency, errors, help | No critical violations |
| **SOC/enterprise** | Status at a glance, severity, storage/health, clarity | Dashboard and operations clarity |

---

## 2. WCAG 2.2 — Gaps by frontend

### 2.1 React (`frontend/`)

| Criterion | Level | Status | Gap / note |
|-----------|--------|--------|------------|
| **1.1.1 Non-text content** | A | Partial | Stream/video: `alt` on live feed img present; canvas/visualizations need text alternative or `aria-label` where they convey info. |
| **1.3.1 Info and relationships** | A | Good | Landmarks (`main`, `nav`), `aria-labelledby` on sections, `role="region"`, labels + `htmlFor`. |
| **1.4.1 Use of color** | A | Good | Severity uses text/labels + color (high/medium/low). |
| **1.4.3 Contrast (minimum)** | AA | Verify | Zinc/cyan palette; ensure body text ≥ 4.5:1, large text ≥ 3:1 (audit with tool e.g. WAVE). |
| **1.4.10 Reflow** | AA | Partial | Some tables/grids may need horizontal scroll at 320px; ensure no 2D scroll required for primary content. |
| **1.4.11 Non-text contrast** | AA | Good | Focus ring (`focus-visible:ring-2`), buttons have sufficient contrast. |
| **1.4.13 Content on hover/focus** | AA | Check | Custom tooltips/popovers: must be dismissible, hoverable, persistent per 1.4.13. |
| **2.1.1 Keyboard** | A | Good | Buttons/links/inputs; F fullscreen when stream focused. Help modal and quick search dialog. |
| **2.1.2 No keyboard trap** | A | Partial | Modal/dialog: focus trap and Esc close present; **ensure focus returns to trigger** on close (e.g. help, quick search). |
| **2.1.4 Character key shortcuts** | A | Good | Shortcuts (e.g. ?) are non–single-letter or documented; no conflict with 2.1.4. |
| **2.4.1 Bypass blocks** | A | **Gap** | **No “Skip to main content” link.** Add a visible or sr-only skip link at top of page. |
| **2.4.3 Focus order** | A | Good | Logical DOM order; no positive `tabIndex` that would break order. |
| **2.4.7 Focus visible** | AA | Good | `*:focus-visible` and `focus-visible:ring-2` in `index.css` and components. |
| **3.1.1 Language of page** | A | Good | `index.html`: `<html lang="en">`. |
| **3.3.1 Error identification** | A | Good | `role="alert"` and `aria-describedby` on login/export errors; `aria-invalid` on inputs. |
| **3.3.2 Labels or instructions** | A | Good | Labels (including `sr-only` where appropriate), placeholders, `aria-label` on icon buttons. |
| **4.1.2 Name, role, value** | A | Good | Buttons, links, inputs, dialogs have names and roles; `aria-busy` on loading buttons. |

**React summary:** Strong on ARIA, keyboard, and errors. **Add skip-to-main-content.** Verify contrast and reflow; confirm focus return on modal close.

---

### 2.2 Legacy HTML (`templates/index.html`, `templates/settings.html`)

| Criterion | Level | Status | Gap / note |
|-----------|--------|--------|------------|
| **1.1.1 Non-text content** | A | Partial | Canvas elements have `aria-label`; ensure all decorative images have `alt=""`. |
| **1.3.1 Info and relationships** | A | Good | `<main>`, `<nav role="navigation" aria-label="Main">`, `<section>`, `role="region"`, `aria-label` on regions; tabs with `role="tab"` and `aria-selected`. |
| **1.4.2 Audio control** | A | Check | If any auto-playing audio > 3s, provide pause/stop or volume control. |
| **2.1.1 Keyboard** | A | Good | Buttons and links; ensure all custom widgets (tabs, dropdowns) are keyboard-operable. |
| **2.4.1 Bypass blocks** | A | **Gap** | **No skip link.** Add “Skip to main content” before nav. |
| **2.4.7 Focus visible** | AA | Good | `*:focus-visible { outline: 2px solid var(--accent); }`. |
| **3.1.1 Language of page** | A | Good | `<html lang="en">` in template. |

**Legacy summary:** Structure and focus are good. **Add skip link;** verify no auto-play audio without control.

---

### 2.3 Plotly Dash (`dashboard/`)

| Criterion | Level | Status | Gap / note |
|-----------|--------|--------|------------|
| **1.1.1 Non-text content** | A | Check | Dash/Plotly charts: ensure `figure` has accessible description or title; images have alt. |
| **1.3.1 Info and relationships** | A | Partial | Sidebar and layout use Bootstrap/Dash; ensure headings (e.g. `role="heading"` or `h1`/`h2`) and landmarks where applicable. |
| **2.1.1 Keyboard** | A | Check | Dash interactivity (dropdowns, buttons) is generally keyboard-accessible; verify tab order and no mouse-only actions. |
| **2.4.1 Bypass blocks** | A | **Gap** | **Skip link not verified.** Add if missing. |
| **2.4.7 Focus visible** | AA | Check | Bootstrap/Dash default focus styles; ensure 3:1 non-text contrast (1.4.11). |

**Dash summary:** Depends on Dash/Bootstrap defaults. **Verify skip link, headings, and chart accessibility.**

---

## 3. Nielsen’s 10 heuristics — Gaps

| # | Heuristic | React | Legacy | Dash | Gap |
|---|-----------|-------|--------|------|-----|
| 1 | **Visibility of system status** | Good (REC, audio, loading, toasts) | Good (REC, status section) | Good (SOC layout) | Ensure long operations show progress or “Generating…” (e.g. incident bundle). |
| 2 | **Match system and real world** | Good (Events, Timeline, Export) | Good | Good | Minor: some terms (e.g. “ai_data”) could have tooltips. |
| 3 | **User control and freedom** | Good (Esc, Dismiss, Back) | Good (Close, Back) | Good | Confirm destructive actions (e.g. Reset data) have explicit confirmation. |
| 4 | **Consistency and standards** | Good (nav, buttons, severity) | Good | Good | Design tokens (spacing, type scale) still optional; see FRONTEND_UI_AUDIT. |
| 5 | **Error prevention** | Good (validation, confirmations) | Good | Good | — |
| 6 | **Recognition rather than recall** | Good (filters, saved searches) | Good (filters visible) | Good | — |
| 7 | **Flexibility and efficiency** | Good (shortcuts, refresh) | Good | Partial | Power-user shortcuts documented in help. |
| 8 | **Aesthetic and minimalist design** | Partial | Partial | Good | Reduce clutter where possible; skeleton loaders already in use (React). |
| 9 | **Help recognize, diagnose, recover from errors** | Good (role="alert", messages) | Good | Good | Plain-language messages. |
| 10 | **Help and documentation** | Good (? help, shortcuts) | Good (Help modal) | Check | Ensure Dash has in-app help or link to docs. |

**Nielsen summary:** No critical failures. Optional: design tokens (8), tooltips for jargon (2), and Dash help (10).

---

## 4. SOC / enterprise dashboard — Gaps

| Area | React | Legacy | Dash | Gap |
|------|-------|--------|------|-----|
| **Status at a glance** | Dashboard cards, system status | Status section, REC | Overview | **Storage/recording health** not in UI (backend can expose; see FRONTEND_UI_AUDIT). |
| **Severity-based prioritization** | Events/timeline severity badges | Severity filters and badges | Alerts page | Done. |
| **Contextual visualization** | Timeline, map, heatmaps | Charts, live activity | Timeline, map | Done. |
| **Alert fatigue reduction** | Filters, ack, summary counts | Filters, ack | Alerts | Done. |
| **Widget / layout flexibility** | Fixed sections | Fixed sections | Dash layout | Optional: configurable dashboard (future). |
| **User management (admin)** | — | — | — | **No UI for user list and site assignment** (backend has `/api/v1/users`, `/api/v1/users/<id>/sites`); see MISSING_UI_BUTTONS. |
| **Refresh / manual control** | Refresh where relevant | Refresh buttons | — | React Dashboard has refresh; ensure legacy “Refresh” for status is visible. |
| **Historical camera health** | — | — | — | **No flapping / last-offline** in UI (research: Boring Toolbox–style). |

---

## 5. Prioritized remediation

### P0 — Must fix (accessibility / compliance)

1. **Skip to main content (all frontends)**  
   - **React:** ✅ Done. Skip link at top of app (visible on focus); `id="main"` on `<main>`.  
   - **Legacy:** ✅ Done. Skip link before `<nav>`; `id="main"` on `<main>`.  
   - **Dash:** ✅ Done. Skip link at top of layout; `id="main-content"` on main content column.  
   - **WCAG:** 2.4.1 Bypass blocks (Level A).

2. **Focus return on modal close (React)**  
   - ✅ Done. Help and Quick search modals return focus to their trigger buttons on close.  
   - **WCAG:** 2.1.2 No keyboard trap, best practice.

### P1 — Should fix (UX / enterprise)

3. **User management UI (React Settings)**  
   - Admin-only section: list users (`GET /api/v1/users`), edit site access (`GET/PUT /api/v1/users/<id>/sites`).  
   - **Ref:** MISSING_UI_BUTTONS.

4. **Contrast and reflow (React + legacy)**  
   - Run WAVE or axe on key pages; fix any contrast < 4.5:1 for text, 3:1 for UI components.  
   - Ensure content reflows at 320px width without horizontal scroll for main content (1.4.10).

5. **Storage / recording health in System Status**  
   - Backend: expose recordings directory size or “low space” flag if feasible.  
   - React (and legacy) Dashboard: show storage/retention status and warning when low.

### P2 — Nice to have

6. **Design tokens (React + legacy)**  
   - Spacing/type scale (e.g. 4/8/16px, font sizes); consistent card padding and section headings.  
   - **Ref:** FRONTEND_UI_AUDIT.

7. **Tooltips for jargon**  
   - e.g. “ai_data”, “integrity_hash”, “legal hold” — short explanation on hover/focus (and ensure 1.4.13 if custom tooltips).

8. **Dash: skip link, headings, chart accessibility**  
   - Add skip link; ensure each page has a logical heading; ensure Plotly figures have accessible names/descriptions.

9. **Historical camera health (flapping / last offline)**  
   - Backend support + Dashboard/React display for camera online/offline history.

---

## 6. How to run a high-grade audit yourself

1. **Automated accessibility**  
   - [WAVE](https://wave.webaim.org/extension/) or [axe DevTools](https://www.deque.com/axe/devtools/) on each frontend (React build, legacy at `/`, Dash if served).  
   - Fix all Level A and AA issues reported.

2. **Keyboard-only pass**  
   - Use Tab, Enter, Space, Esc; no mouse. Ensure every action is reachable and focus never trapped; skip link is first focusable.

3. **Screen reader spot check**  
   - VoiceOver (macOS) or NVDA (Windows): navigate Dashboard, Live, Events, Login, Export. Check announcements for status, errors, and dialogs.

4. **Contrast**  
   - Use [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/) or DevTools on text and UI components; aim 4.5:1 (text), 3:1 (large text and graphics).

5. **Heuristic review**  
   - One pass per Nielsen heuristic (e.g. “Visibility of system status”): list violations and rate severity.  
   - **Ref:** [How to Conduct a Heuristic Evaluation](https://www.nngroup.com/articles/how-to-conduct-a-heuristic-evaluation/).

6. **Responsive / reflow**  
   - Resize to 320px width; zoom 200%; ensure no loss of content or 2D scroll for primary flows.

---

## 7. File reference

| Frontend | Key files |
|----------|-----------|
| React | `frontend/src/App.tsx`, `frontend/src/views/*.tsx`, `frontend/src/index.css`, `frontend/index.html` |
| Legacy | `templates/index.html`, `templates/settings.html` |
| Dash | `dashboard/app.py`, `dashboard/components/sidebar.py`, `dashboard/pages/*.py`, `dashboard/assets/custom.css` |

**Related docs:** [FRONTEND_UI_AUDIT.md](FRONTEND_UI_AUDIT.md) (score 78/100, design and features), [MISSING_UI_BUTTONS.md](MISSING_UI_BUTTONS.md) (backend–frontend parity), [APP_REVIEW_AND_RATING.md](APP_REVIEW_AND_RATING.md).
