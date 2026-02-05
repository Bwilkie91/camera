# Enterprise & Government Standards — Improvements & Integrations

This document summarizes **improvements and integrations** implemented to align the system with enterprise and government highest standards, and points to detailed references. It complements **GOVERNMENT_STANDARDS_AUDIT.md**, **ENTERPRISE_ROADMAP.md**, and **AI_DETECTION_LOGS_STANDARDS.md**.

---

## 1. Standards Reference (2025–2026)

| Standard | Focus |
|----------|--------|
| **NIST SP 800-171r3** | CUI protection; access control, audit, encryption |
| **NIST SP 800-53 (AU, IA, AC)** | Audit, identification/auth, access control |
| **NIST IR 8523 / CJIS 6.0** | MFA for CJIS; authenticator management |
| **NISTIR 8161 Rev.1** | CCTV export: chain of custody, metadata, integrity |
| **NIST SP 1800-35** | Zero Trust Architecture |
| **ISO/IEC 27001:2022** | ISMS; crypto, key management, audit |
| **FIPS 140-2** | Cryptographic modules; encryption at rest/transit |

---

## 2. Implemented Improvements & Integrations

### 2.1 Audit & Accountability (NIST AU-9, CJIS)

- **Audit log integrity**
  - Per-row `integrity_hash` (SHA-256) on insert; **GET /audit_log/verify** to detect tampering.
  - **UI**: Settings → “Export audit log (CSV)” and **“Verify audit log”** (admin).
- **Audit log export**
  - **GET /audit_log/export** with SHA-256 and chain-of-custody metadata; CSV download.
  - **UI**: Settings → “Export audit log (CSV)” (admin).

### 2.2 AI Detection & Event Logs (NISTIR 8161, NIST AI 100-4, SWGDE)

- **Provenance and integrity**
  - `timestamp_utc`, `model_version`, `system_id`, `integrity_hash` on ai_data and events.
  - **GET /api/v1/ai_data/verify** for detection-log integrity.
  - **UI**: Export → “Export AI Data (CSV)” and **“Verify detection log”**.
- **Export metadata**
  - CSV and response headers: `X-Export-UTC`, `X-Operator`, `X-System-ID`, `X-Export-SHA256`.
  - **UI**: Export page describes chain-of-custody; Verify shows verified/mismatched/total.

See **docs/AI_DETECTION_LOGS_STANDARDS.md** for full alignment.

### 2.3 Video / Recording Export (NISTIR 8161, ONVIF)

- **Recording export**
  - **GET /recordings**, **GET /recordings/<name>/export** with NISTIR-style headers (`X-Export-UTC`, `X-Operator`, `X-System-ID`, `X-Camera-ID`, `X-Export-SHA256`).
  - **?format=mp4** when ffmpeg is available.
  - **UI**: Export → per-recording **AVI**, **MP4**, and **“View manifest”**.
- **Recording manifest**
  - **GET /recordings/<name>/manifest** returns JSON manifest (metadata + SHA-256) without downloading the file.
  - **UI**: Export → **“View manifest”** per recording; manifest shown in-page with Close.

### 2.4 Access Control & Authentication

- **RBAC and resource-level access**
  - Roles: viewer, operator, admin. **user_site_roles**: per-site access; events, get_data, aggregates, search, export scoped by allowed sites.
  - **API**: GET/PUT **/api/v1/users/<id>/sites** (admin). *UI for user/site management: see **docs/MISSING_UI_BUTTONS.md**.*
- **MFA (TOTP)**
  - Optional TOTP; ENABLE_MFA=1; setup/confirm in Settings; verify at login (NIST IR 8523 / CJIS 6.0).
- **Password policy**
  - Min length, digit, special; **PASSWORD_EXPIRY_DAYS**, **PASSWORD_HISTORY_COUNT**; **/me**, **POST /change_password**; login rejects expired.
- **Session timeout & lockout**
  - SESSION_TIMEOUT_MINUTES; LOCKOUT_MAX_ATTEMPTS / LOCKOUT_DURATION_MINUTES; 401/423 handling.

### 2.5 Security Headers & HTTPS

- **Headers**: X-Content-Type-Options, X-Frame-Options; optional HSTS; **CONTENT_SECURITY_POLICY** (env).
- **HTTPS**: **ENFORCE_HTTPS=1** redirects HTTP→HTTPS; X-Forwarded-Proto respected.

### 2.6 Operational & Scalability

- **Health**: `/health` (liveness), `/health/ready` (readiness).
- **Multi-instance**: Optional **REDIS_URL** for WebSocket event broadcast across instances.
- **System status**: **GET /api/v1/system_status** (DB, uptime, per-camera status, storage); Dashboard display.
- **Camera autodetect**: **GET /api/v1/cameras/detect**; **UI**: Dashboard “Detect cameras”.

### 2.7 Analytics & Configuration (Admin)

- **Analytics config**
  - **GET /config**, **PATCH /config** (loiter_seconds, loiter_zones, crossing_lines); changes audited.
  - **UI**: Settings → Analytics config (admin): loiter zones, loiter seconds, crossing lines + Save.

---

## 3. Integration Points (APIs Used by UI)

| Feature | Backend | Frontend |
|---------|---------|----------|
| Audit log list | GET /audit_log | Settings (admin) |
| Audit log export | GET /audit_log/export | Settings “Export audit log (CSV)” |
| Audit log verify | GET /audit_log/verify | Settings “Verify audit log” |
| AI data export | GET /export_data | Export “Export AI Data (CSV)” |
| AI data verify | GET /api/v1/ai_data/verify | Export “Verify detection log” |
| Recordings list | GET /recordings | Export |
| Recording export AVI/MP4 | GET /recordings/<name>/export | Export AVI / MP4 |
| Recording manifest | GET /recordings/<name>/manifest | Export “View manifest” |
| Config (analytics) | GET /config, PATCH /config | Settings (admin) |
| Users/sites | GET/PUT /api/v1/users/<id>/sites | *See MISSING_UI_BUTTONS.md* |

---

## 4. Remaining Gaps (from GOVERNMENT_STANDARDS_AUDIT)

- **Encryption at rest**: App-level not implemented; README recommends LUKS/vault for DB and recordings.
- **Key management**: Policy/lifecycle (ISO A.8.24) not implemented.
- **TLS enforcement**: Documented “use HTTPS”; ENFORCE_HTTPS supports redirect.
- **Vulnerability management**: No formal CVE/dependency-scan process.
- **Legal hold**: No formal hold/export workflow beyond current export.

---

## 5. Related Docs

- **GOVERNMENT_STANDARDS_AUDIT.md** — Gap analysis, scores, Tier 1–4 recommendations.
- **ENTERPRISE_ROADMAP.md** — Scalability, AI/ML extension points, phase checklist.
- **AI_DETECTION_LOGS_STANDARDS.md** — AI/event log provenance, integrity, export.
- **RESEARCH_IMPROVEMENTS_ACADEMIC_LE.md** — Academic and law enforcement sources; concrete code improvements (fixity, ONVIF, SWGDE, CADF, cross-camera, NL search).
- **MISSING_UI_BUTTONS.md** — Scan of missing or suggested UI buttons and links.
