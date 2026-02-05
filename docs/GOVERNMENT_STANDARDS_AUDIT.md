# Government & Best-in-Class Standards Audit

Comparison of the Vigil (Edge Video Security) system against government and high-assurance standards, with ratings and recommendations. Updated for **2025–2026** alignment.

---

## Reference Standards

| Standard | Scope |
|----------|--------|
| **NIST SP 800-171r3** | Protecting CUI in nonfederal systems; access control, audit, encryption. |
| **NIST SP 800-53 (AU, IA, AC)** | Federal security controls: audit events, protection of audit info, identification/auth, access control. |
| **NIST IR 8523 (Sept 2025)** | Multi-Factor Authentication for CJIS: implementation considerations, design principles. |
| **CJIS Security Policy 6.0** | Effective late 2024; MFA required for CJI; modernized authenticator management. |
| **NISTIR 8161 Rev.1** | CCTV digital video export: chain of custody, metadata (UTC, operator, equipment), digital signatures. |
| **NIST SP 1800-35 (ZTA)** | Zero Trust Architecture implementations (2025). |
| **ISO/IEC 27001:2022** | ISMS: cryptography policy, key management, access control, audit. |
| **FIPS 140-2** | Cryptographic modules for government; encryption at rest/transit. |

---

## Gap Analysis by Domain

### 1. Access Control & Authentication

| Requirement | Government / Best-in-Class | Current System | Gap |
|-------------|----------------------------|----------------|-----|
| RBAC | CJIS/NIST: roles limit access to functions and data | Viewer, Operator, Admin; **resource-level**: user_site_roles (per-site access); GET/PUT /api/v1/users/<id>/sites; events, get_data, aggregates, search, export scoped by allowed sites | **Done** |
| MFA | CJIS 6.0 / NIST IR 8523: multi-factor authentication | **Implemented**: Optional TOTP (pyotp); ENABLE_MFA=1; setup/confirm in Settings; verify_totp at login | **Done** (optional) |
| Password policy | Strong complexity, expiry, history | **Implemented**: min length, digit, special; **PASSWORD_EXPIRY_DAYS**, **PASSWORD_HISTORY_COUNT**; GET /me, POST /change_password; login rejects expired, returns password_expires_in_days | **Done** |
| Session timeout | Inactivity timeout; re-auth for sensitive actions | **Implemented**: SESSION_TIMEOUT_MINUTES; 401 + session_timeout redirect | **Done** |
| Account lockout | After N failed logins (NIST AC-7 / CJIS) | **Implemented**: LOCKOUT_MAX_ATTEMPTS (5), LOCKOUT_DURATION_MINUTES (15); 423 when locked | **Done** |

### 2. Audit & Accountability

| Requirement | Government / Best-in-Class | Current System | Gap |
|-------------|----------------------------|----------------|-----|
| AU-2 Event types | Log auth, privilege use, config changes, exports | Login, logout, **login_failed with IP/User-Agent**, export_data, **export_audit_log**, acknowledge_event, **toggle_recording, move_camera**, **config_change** | **Done** (config PATCH audited). |
| AU-9 Protection | Protect audit logs from modification/deletion; integrity | **Audit log never deleted by RETENTION_DAYS**; separate AUDIT_RETENTION_DAYS; **GET /audit_log/export** with SHA-256 and **per-row integrity_hash**; **GET /audit_log/verify** to detect tampering | **Done** |
| Retention of audit | Defined retention; separate from operational data | **Implemented**: AUDIT_RETENTION_DAYS (0 = never); retention job deletes audit_log only when set | **Done** |
| Immutability | NIST enhancement: cryptographic protection of audit | **Per-row integrity_hash** (SHA-256 of row content) stored on insert; export includes hashes; **/audit_log/verify** for verification | **Done** |

### 3. Data Protection & Encryption

| Requirement | Government / Best-in-Class | Current System | Gap |
|-------------|----------------------------|----------------|-----|
| Encryption at rest | FIPS 140-2 / ISO: DB and recordings encrypted | SQLite and AVI on filesystem; no app-level encryption | **Missing** |
| Encryption in transit | TLS for all endpoints | Documented as “use HTTPS in production”; not enforced | **Partial** |
| Key management | Policy and lifecycle (ISO A.8.24) | N/A | **Missing** |

### 4. Video Export & Chain of Custody

| Requirement | Government / Best-in-Class | Current System | Gap |
|-------------|----------------------------|----------------|-----|
| NISTIR 8161 / ONVIF export | Standard container (e.g. MP4), UTC timestamps, operator/metadata, digital signature | **Video**: GET /recordings, /recordings/<name>/export with **X-Export-UTC, X-Operator, X-System-ID, X-Camera-ID, X-Export-SHA256**; **?format=mp4** for MP4 when ffmpeg available; manifest endpoint. | **Done** |
| Export metadata | Operator, time, equipment, frame-accurate time | **Present**: Export UTC, operator, system ID in CSV header | **Done** (for CSV). |
| Integrity of export | Digital signature for evidence | **SHA-256 of export content** in CSV footer and response header (verifiable chain) | **Done** (for CSV). |

### 5. Operational Security

| Requirement | Government / Best-in-Class | Current System | Gap |
|-------------|----------------------------|----------------|-----|
| Secure defaults | No default credentials; secrets from env | Default admin/admin; secrets via env | **Partial** |
| Security headers | HSTS, CSP, etc. | **Implemented**: X-Content-Type-Options, X-Frame-Options; optional HSTS; **CSP via CONTENT_SECURITY_POLICY env** | **Done** (CSP configurable). |
| Input validation | All inputs validated/sanitized | Some validation; no centralized schema | **Partial** |
| Dependency hygiene | Known vulnerabilities; updates | requirements.txt pinned; no CVE process | **Partial** |

### 6. Retention & Compliance

| Requirement | Government / Best-in-Class | Current System | Gap |
|-------------|----------------------------|----------------|-----|
| Defined retention | Policy for video, AI data, audit, logs | RETENTION_DAYS for ai_data, events, recordings; not audit_log | **Partial** |
| Legal hold / export for disclosure | Ability to preserve and export for legal | Export CSV; no formal hold or NISTIR-style export | **Partial** |

---

## Overall Rating (1–100)

| Category | Weight | Score (0–100) | Weighted |
|----------|--------|----------------|----------|
| Access Control & Auth | 20% | 92 | 18.4 |
| Audit & Accountability | 25% | 88 | 22.0 |
| Data Protection & Encryption | 20% | 30 | 6.0 |
| Video Export & Chain of Custody | 15% | 82 | 12.3 |
| Operational Security | 10% | 78 | 7.8 |
| Retention & Compliance | 10% | 75 | 7.5 |
| **Total** | 100% | — | **74.0** |

**Rounded overall score: 74/100** for government / best-in-class alignment (up from 69; 39 baseline). See **docs/SYSTEM_RATING.md** for the score breakdown and path to higher ratings.

- **Strengths**: **Resource-level RBAC** (user_site_roles, per-site filtering), RBAC roles, optional TOTP MFA, **password expiry and history** (PASSWORD_EXPIRY_DAYS, PASSWORD_HISTORY_COUNT, /change_password, /me), session timeout, account lockout, password policy, audit with IP/User-Agent and config_change, per-row audit integrity_hash and GET /audit_log/verify, separate audit retention, audit log export with SHA-256, **optional MP4 recording export (?format=mp4)**, video recording export with metadata + SHA-256, configurable CSP, HTTPS enforcement, FIPS/crypto scope documented, incident response procedures, security headers, retention job, encryption-at-rest guidance, keyboard shortcut ? for help.
- **Remaining gaps**: Encryption at rest (app-level); key management; TLS enforcement; input validation schema; dependency CVE process; formal legal hold.

---

## Recommendations to Reach Best-in-Class

### Tier 1 (High impact, high alignment)

1. ~~**Session timeout**~~ – **Done**: SESSION_TIMEOUT_MINUTES; 401 + session_timeout; frontend redirect to login.
2. ~~**Expand audit events**~~ – **Done**: Recording, PTZ, login_failed with IP/User-Agent (NIST AU-2).
3. ~~**Protect audit log**~~ – **Done**: Audit log never deleted by RETENTION_DAYS; separate AUDIT_RETENTION_DAYS. Optional next: append-only or checksums.
4. ~~**Password policy**~~ – **Done**: PASSWORD_MIN_LENGTH, PASSWORD_REQUIRE_DIGIT, PASSWORD_REQUIRE_SPECIAL; **PASSWORD_EXPIRY_DAYS**, **PASSWORD_HISTORY_COUNT**; GET /me, POST /change_password; login rejects expired password.
5. ~~**Export metadata**~~ – **Done**: UTC, operator, system ID in CSV; **SHA-256 in footer and X-Export-SHA256 header** (NISTIR-style integrity).

### Tier 2 (Evidence & compliance)

6. ~~**Video export profile**~~ – **Done**: GET /recordings, GET /recordings/<name>/export with **X-Export-UTC, X-Operator, X-System-ID, X-Camera-ID, X-Export-SHA256**; **?format=mp4** for MP4 when ffmpeg available; GET /recordings/<name>/manifest (JSON).
7. **Encryption at rest** – **Documented**: README recommends LUKS/vault for DB and recordings; key lifecycle (ISO A.8.24). Optional app-level encryption still pending.
8. ~~**HTTPS enforcement**~~ – **Done**: ENFORCE_HTTPS=1 redirects HTTP→HTTPS; respects X-Forwarded-Proto; document reverse proxy in README.

### Tier 3 (Government / high assurance)

9. ~~**MFA**~~ – **Done**: Optional TOTP (pyotp); ENABLE_MFA=1; NIST IR 8523 / CJIS 6.0 aligned; setup in Settings, verify at login.
10. ~~**Account lockout**~~ – **Done**: LOCKOUT_MAX_ATTEMPTS (5), LOCKOUT_DURATION_MINUTES (15); 423 + locked_until_utc.
11. ~~**Security headers**~~ – **Done**: X-Content-Type-Options, X-Frame-Options; optional HSTS; CSP via CONTENT_SECURITY_POLICY.
12. ~~**FIPS / crypto**~~ – **Documented**: README § Security describes FIPS 140-2 scope (OpenSSL/Python, approved algorithms); TLS and hashing compliance scope.

### Tier 4 (Process & ops)

13. ~~**Retention for audit_log**~~ – **Done**: AUDIT_RETENTION_DAYS; audit_log only pruned by that; never by RETENTION_DAYS.
14. ~~**Incident response**~~ – **Done**: **docs/INCIDENT_RESPONSE.md** — procedures for audit tampering, breach, evidence preservation, and operational notes.
15. **Vulnerability management** – Process for updating dependencies and addressing CVEs; optional automated scanning.

---

## Summary

The system now **scores ~74/100** with **resource-level RBAC** (user_site_roles, per-site filtering), **password expiry and history**, **optional MP4 export** (?format=mp4), audit log integrity, FIPS/crypto documentation, incident response procedures, and keyboard accessibility. Remaining gaps: encryption at rest (app-level), key management, TLS enforcement, dependency CVE process.

---

## Frontend & UX (best-in-class alignment)

Reference: Enterprise VMS (e.g. Milestone XProtect Smart Client, Genetec), SOC dashboards, and UX best practices (clear layout, responsive controls, real-time feedback, data visualization, accessibility).

| Criterion | Best-in-class | Current system | Status |
|-----------|----------------|----------------|--------|
| **At-a-glance dashboard** | Summary metrics, recording status, event counts, system health | **Dashboard** view: recording, events today, unacknowledged count, streams, health | **Done** |
| **Real-time feedback** | Alerts/toasts when new events; immediate response to actions | **Toast** on new event (WebSocket at app level); recording/PTZ state updates | **Done** |
| **Timeline / history** | Date-range filter, severity, navigable event list | **Timeline**: Last 24h / 7 days / All; severity badges; events by time | **Done** |
| **Map / sites** | Multi-site support, camera positions on map | **Map**: Site selector when multiple sites; camera positions; fallback when no map_url | **Done** |
| **Tooltips / help** | Key actions explained; reduced learning curve | **Tooltips** (title) on Record, PTZ, Export AI Data, Download evidence | **Done** |
| **Consistent layout** | Nav, header, main; predictable structure | Nav (Dashboard, Live, Events, Timeline, Map, Analytics, Export, Settings); header with logout | **Done** |
| **Data visualization** | Charts, aggregates for insights | **Analytics** view with aggregates table; **Events** search | **Done** |
| **Responsive controls** | Buttons, filters, quick actions | Grid layout (Live); filters (Timeline, Events search); recording/PTZ in Live | **Done** |
| **Accessibility** | Keyboard, ARIA, contrast | **?** opens help modal (keyboard shortcuts); Esc closes; toast with role="status" aria-live; semantic HTML; contrast (zinc/cyan) | **Done** |
| **Customizable views** | User-configurable layouts, saved views | Fixed views; no saved layouts | **Partial** |

**Summary**: Frontend meets enterprise-style at-a-glance dashboard, real-time event notification, timeline with filters, multi-site map, tooltips, **? keyboard shortcut for help**, and consistent navigation. Optional next: customizable dashboard widgets or saved filters.

---

## Path to 2026 Best-in-Class (research-aligned)

| Priority | Item | Standard / source | Status |
|----------|------|-------------------|--------|
| 1 | MFA (TOTP) | NIST IR 8523, CJIS 6.0 | **Done** (optional) |
| 2 | CSP | 2025/2026 hardening | **Done** (env) |
| 3 | Zero Trust alignment | NIST SP 1800-35, continuous verification | Partial (session + MFA) |
| 4 | Video export (metadata + SHA-256) | NISTIR 8161, ONVIF | **Done** (recordings export + manifest) |
| 5 | Encryption at rest | FIPS 140-2, ISO 27001 | Documented (LUKS/vault in README) |
| 6 | Audit immutability | AU-9 enhancement | **Done** (per-row integrity_hash, /audit_log/verify) |
| 7 | Password expiry / history | NIST/CJIS | **Done** (PASSWORD_EXPIRY_DAYS, PASSWORD_HISTORY_COUNT, /change_password) |
| 8 | Resource-level RBAC | CJIS/NIST | **Done** (user_site_roles, GET/PUT /api/v1/users/<id>/sites; events/data/export scoped) |
| 9 | MP4 export | NISTIR 8161 | **Done** (?format=mp4 when ffmpeg available) |

References: NIST IR 8523 (MFA for CJIS, Sept 2025); CJIS Security Policy v6.0 (late 2024); NIST SP 1800-35 (ZTA, 2025); PE-6(3) video surveillance (SP 800-53 R5).
