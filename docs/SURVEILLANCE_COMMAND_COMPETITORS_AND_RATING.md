# Surveillance Command — Competitor Research, Must-Add List & Government/Enterprise Rating

This document (1) summarizes **Surveillance Command (Vigil)** competitors and differentiators, (2) lists **must-add configurations, dependencies, and technology upgrades**, and (3) rates the current system **1–100** against highest government and enterprise standards.

**2025–2026 update:** See **COMPETITORS_AND_STANDARDS_2026.md** for Rhombus/Verkada AI search (sub-second, NL), ONVIF/NISTIR 8161 alignment, and dependency/API improvement priorities.

---

## 1. Competitor Overview

### 1.1 Main Competitors (SOC / Enterprise VMS)

| Competitor | Positioning | Key differentiators | Typical deployment |
|------------|-------------|---------------------|---------------------|
| **Verkada** | All-in-one cloud (cameras, access, sensors, intercom) | AI Unified Timeline, native AWS cloud, 2–12 week implementation | Cloud-native; hardware + SaaS bundle |
| **Rhombus** | Open, flexible; modernize existing cameras | ChatGPT-style NL search, sub-second search, Brivo/Genea integrations, Rhombus Relay for legacy cameras | Cloud + on-prem relay; 3–12 week phased |
| **Genetec (Security Center / Omnicast)** | Unified security platform, VMS + access + ALPR | Centralized management, broad IP camera support, 4.4/5 Gartner, 93% recommend | On-prem / hybrid; complex setup |
| **Milestone XProtect** | Enterprise VMS, open platform | Scalable (100–1000+ cameras), Smart Client, deep integrations, K8s-ready options | On-prem / hybrid; enterprise scale |
| **Avigilon (Motorola)** | Cloud-native, off-the-shelf devices | Cloud VMS, open to third-party cameras; strong LPR and analytics | Cloud + edge |
| **Eagle Eye Networks** | Cloud VMS | 24/7 cloud recording, bandwidth-efficient, NDAA options | Cloud-first |
| **Immix / SureView** | SOC / remote monitoring | Focus on SOC operator workflow, false-alarm reduction, AI triage | SOC / NOC |
| **Hanwha / Vivotek (NDAA)** | Hardware + firmware | NDAA/TAA compliant cameras, H.265, WiseStream, AI on camera | Gov / federal procurement |

### 1.2 Competitor Features We Should Match or Exceed

- **AI analytics**: Motion, people/vehicle count, facial recognition (privacy-aware), LPR, activity indexing, NL search.
- **Cloud / hybrid**: Redundant storage, offline streaming, unlimited or tiered clip storage.
- **Security**: End-to-end encryption, NDAA/TAA compliance (for federal), encrypted storage, MFA.
- **Management**: Single console, RBAC, 24/7 remote access, mobile apps (iOS/Android).
- **Integration**: REST/API, alarm monitoring, webhooks, MQTT, professional monitoring.
- **SOC-specific**: False-alarm reduction, operator fatigue mitigation, AI triage, sub-second search.
- **Standards**: NISTIR 8161 (CCTV export), CJIS 6.0 (MFA, audit), ONVIF/PSIA, MP4/H.264 for evidence.

---

## 2. Must-Add Configurations

These are **configuration and environment** additions (no new code required, or minimal) to align with enterprise and government practice.

| Configuration | Purpose | Standard / competitor | Priority |
|---------------|--------|------------------------|----------|
| **ENFORCE_HTTPS=1** in production | TLS for all traffic | NIST, CJIS, ISO 27001 | P0 |
| **ENABLE_MFA=1** for operators/admins | MFA for CJI access | CJIS 6.0, NIST IR 8523 | P0 |
| **PASSWORD_EXPIRY_DAYS**, **PASSWORD_HISTORY_COUNT** | Password lifecycle | NIST/CJIS | P0 (already exist; enforce in deployment) |
| **SESSION_TIMEOUT_MINUTES** | Inactivity timeout | CJIS, NIST | P0 |
| **LOCKOUT_MAX_ATTEMPTS** / **LOCKOUT_DURATION_MINUTES** | Account lockout | NIST AC-7 | P0 |
| **CONTENT_SECURITY_POLICY** (CSP) | Mitigate XSS/clickjacking | 2025/2026 hardening | P1 |
| **REDIS_URL** (when multi-instance) | WebSocket broadcast across instances | Scale, SOC multi-node | P1 |
| **AUDIT_RETENTION_DAYS** (separate from RETENTION_DAYS) | Audit log retention policy | NIST AU-11 | P1 |
| **STREAM_JPEG_QUALITY**, **STREAM_MAX_WIDTH** | Tune live stream vs latency | Operational | P2 |
| **YOLO_DEVICE**, **YOLO_IMGSZ**, **YOLO_CONF** | Detection performance vs accuracy | Enterprise tuning | P2 |
| **Storage path for recordings** (external/NAS) | Capacity and retention | Enterprise | P2 |
| **SUMMARIZATION_WEBHOOK_URL** (optional) | NL summarization hook | Next-gen AI (roadmap) | P3 |
| **ALERT_SMS_URL** / Twilio | Notifications | SOC alerting | P3 |

---

## 3. Must-Add Dependencies

Dependencies to **add or formally support** for government/enterprise and competitor parity.

| Dependency | Use case | Notes |
|------------|----------|--------|
| **pyotp** | TOTP MFA (NIST IR 8523 / CJIS 6.0) | Already optional in requirements; document as required for CJIS deployments |
| **redis** | Multi-instance WebSocket event broadcast | Optional; set REDIS_URL |
| **onvif-zeep** | ONVIF PTZ control | Optional; ONVIF_HOST/USER/PASS |
| **ffmpeg** (system) | MP4 export (NISTIR 8161 Level 0) | Already used when available; document as recommended |
| **cryptography** (FIPS build) or **PyNaCl** | Optional app-level encryption at rest | For encryption-at-rest roadmap |
| **pip-audit** or **safety** | CVE/dependency scanning in CI | Vulnerability management (Tier 4) |
| **pydantic** or **marshmallow** | Request validation for /api/v1/* | Input validation (NIST, operational security) |
| **structlog** or **python-json-logger** | Structured, machine-parseable logs | SOC/enterprise logging |
| **opentelemetry-api** (optional) | Observability (traces/metrics) | Enterprise ops |
| **gunicorn** / **uvicorn** | Production ASGI/WSGI server | Replace dev server in production |

---

## 4. Technology Upgrades

Upgrades that materially improve compliance, scale, or feature parity with competitors.

| Upgrade | Description | Standard / competitor | Priority |
|---------|-------------|----------------------|----------|
| **Encryption at rest** | Encrypt SQLite and recording files (e.g. LUKS at OS, or app-level with key management) | FIPS 140-2, ISO 27001 | P0 |
| **TLS enforcement** | Reject non-HTTPS in production; document reverse proxy | CJIS, NIST | P0 |
| **Key management guidance** | Document key lifecycle, rotation, storage (e.g. vault) | ISO A.8.24 | P1 |
| **Dependency / CVE process** | `pip audit` in CI; schedule dependency updates | Operational security | P1 |
| **Centralized input validation** | Validate limit/offset/dates for all v1 APIs | NIST, OWASP | P1 |
| **Legal hold workflow** | Flag evidence for preservation; export bundle with chain of custody | Legal/compliance | P1 |
| **NISTIR 8161 Level 0 export** | MP4, H.264, embedded time codes, XMP metadata | NISTIR 8161 Rev.1 | P1 (MP4 + headers done; full Level 0 doc) |
| **NDAA/TAA compliance documentation** | Document use of compliant cameras and supply chain | Federal procurement | P2 |
| **HLS or WebRTC option** | Lower latency / scale for many viewers | Competitor (Rhombus, Verkada) | P2 |
| **Natural language search** | Semantic/LLM-backed search over events and clips | Rhombus, next-gen VMS | P2 |
| **Mobile app or PWA** | 24/7 remote access, push alerts | Competitors | P2 |
| **Heatmap API** | Dwell time, counts per zone, time buckets | Enterprise analytics | P2 |
| **Saved searches / search audit** | Saved filters; log search queries (NIST AU-9) | SOC, compliance | P2 |
| **Zero Trust alignment** | Continuous verification, device posture (doc or light implementation) | NIST SP 1800-35 | P3 |
| **K8s / Helm** | Official deployment manifests | Scale (ENTERPRISE_ROADMAP) | P3 |

---

## 5. Rating: Surveillance Command vs Government & Enterprise Standards

### 5.1 Methodology

- **100** = Full alignment with NIST (800-171, 800-53, IR 8161), CJIS 6.0, NIST IR 8523 (MFA), ISO 27001, FIPS 140-2, and enterprise SOC feature set (RBAC, audit, export, search, multi-site, health, scalability options).
- Categories are weighted by impact on government/compliance and enterprise readiness.
- Score reflects **current state** of the Vigil codebase and docs (audit, GOV standards, SYSTEM_RATING, ENTERPRISE_ROADMAP).

### 5.2 Category Scores (1–100)

| Category | Weight | Score | Rationale |
|----------|--------|-------|------------|
| **Access Control & Authentication** | 20% | 92 | RBAC (viewer/operator/admin), resource-level (user_site_roles), optional TOTP MFA, password policy + expiry + history, session timeout, account lockout. Gap: MFA not default for all operators. |
| **Audit & Accountability** | 25% | 88 | Auth, config, export, recording events; per-row integrity_hash; /audit_log/verify; SHA-256 export; separate audit retention. Gap: Search-query audit optional. |
| **Data Protection & Encryption** | 20% | 30 | No app-level encryption at rest; TLS documented (ENFORCE_HTTPS) but not always enforced in practice; key management not implemented. |
| **Video Export & Chain of Custody** | 15% | 82 | NISTIR-style headers (X-Export-UTC, X-Operator, X-System-ID, X-Camera-ID, X-Export-SHA256); MP4 when ffmpeg available; manifest endpoint. Gap: Full NISTIR 8161 Level 0 (e.g. MISB time codes) not documented. |
| **Operational Security** | 10% | 78 | Security headers (CSP, HSTS configurable); secure defaults partial (default admin warning); input caps; no formal CVE process. |
| **Retention & Compliance** | 10% | 75 | RETENTION_DAYS, AUDIT_RETENTION_DAYS; legal hold not formalized; export for disclosure present but no formal hold workflow. |

**Feature parity (competitor context, not in numeric score):** Live streams, grid presets, quick search (Ctrl+K), FPS, multi-site, system status, health, Redis option, aggregates (~72 vs competitors). Gaps: no NL search, no mobile app, no HLS/WebRTC, no heatmap UI.

### 5.3 Overall Score

**Weighted total: 74 / 100**

- **Formula** (same weights as GOVERNMENT_STANDARDS_AUDIT):  
  (92×0.20) + (88×0.25) + (30×0.20) + (82×0.15) + (78×0.10) + (75×0.10) = **18.4 + 22.0 + 6.0 + 12.3 + 7.8 + 7.5 = 74.0**.  
  **74/100** is the **current Surveillance Command rating** against highest government and enterprise standards.

### 5.4 Interpretation

| Band | Score | Meaning |
|------|-------|--------|
| **90–100** | Best-in-class | Encryption at rest, key management, enforced TLS, CVE process, legal hold, full NISTIR 8161, NDAA doc, NL search, mobile/PWA. |
| **80–89** | Strong | Current strengths + encryption at rest (or documented LUKS), enforced HTTPS, dependency audit in CI. |
| **70–79** | **Current** | Strong auth/audit/export; gaps in encryption at rest, key management, formal CVE process, legal hold. |
| **60–69** | Adequate | Core RBAC and audit; missing MFA, password lifecycle, or export integrity. |
| **&lt;60** | Below bar | Significant gaps in access control, audit, or evidence export for government/enterprise. |

### 5.5 Path to 85+

1. **Encryption at rest** (app or LUKS/vault) + key management doc → +8–10.
2. **Enforced TLS** in production + reverse-proxy doc → +2.
3. **Dependency/CVE process** (e.g. `pip audit` in CI) → +2.
4. **Legal hold workflow** (hold flag, export bundle) → +2.
5. **Full NISTIR 8161 Level 0** (time codes, XMP) doc or implementation → +1–2.
6. **Saved searches + search audit log** → +1.

---

## 6. Summary Tables

### Must-Add Checklist (by priority)

| P0 | P1 | P2 | P3 |
|----|----|----|-----|
| ENFORCE_HTTPS=1 in prod | REDIS_URL when multi-instance | STREAM_* / YOLO_* tuning | SUMMARIZATION_WEBHOOK_URL |
| ENABLE_MFA=1 for operators | CSP configured | Storage path (NAS/external) | ALERT_SMS_URL |
| Encryption at rest (or LUKS doc) | Key management guidance | NDAA/TAA doc | Zero Trust doc |
| TLS enforcement | CVE/dependency process | HLS/WebRTC option | K8s/Helm |
| | Input validation (v1 APIs) | NL search | |
| | Legal hold workflow | Heatmap API, saved searches | |
| | NISTIR 8161 Level 0 doc | Mobile/PWA | |

### Competitor vs Vigil (high level)

| Capability | Verkada / Rhombus / Genetec | Vigil (current) |
|------------|-----------------------------|------------------|
| RBAC + resource-level | Yes | Yes (user_site_roles) |
| MFA | Yes | Yes (optional TOTP) |
| Audit + integrity | Varies | Yes (per-row hash, verify) |
| Video export (metadata + hash) | Yes | Yes (NISTIR-style) |
| MP4 export | Yes | Yes (when ffmpeg) |
| NL / semantic search | Rhombus, others | Keyword + filters (extension point) |
| Cloud / redundant storage | Common | Self-hosted; optional Redis |
| Encryption at rest | Common | Documented (LUKS); not in-app |
| Mobile app | Common | No (responsive web) |
| HLS/WebRTC | Common | MJPEG (HLS/WebRTC roadmap) |
| NDAA/TAA | Some | Document only |
| Sub-second search | Rhombus | API &lt;2s target |

---

## 7. 2025–2026 Update

For **latest competitor AI/search features** (Rhombus sub-second NL search, Verkada AI search, ChatGPT-style search) and **NIST/ONVIF 2025** (ONVIF Export, media signing, per-frame UTC), see **COMPETITORS_AND_STANDARDS_2026.md**. That doc also summarizes dependency and API validation improvements.

---

## 8. References

- **NISTIR 8161 Rev.1** — CCTV digital video export (chain of custody, metadata).
- **CJIS Security Policy 6.0** — MFA, audit, encryption.
- **NIST IR 8523** — MFA for CJIS.
- **GOVERNMENT_STANDARDS_AUDIT.md** — Gap analysis and Tier 1–4 recommendations.
- **SYSTEM_RATING.md** — Current 74/100 breakdown.
- **ENTERPRISE_GOV_STANDARDS_IMPROVEMENTS.md** — Implemented improvements.
- **ENTERPRISE_ROADMAP.md** — Scalability and AI/ML extension points.
- **REALTIME_PLAYBACK_AND_QUICK_SEARCH_2026.md** — Live and search standards.
- Competitor / market: Gartner Peer Insights (Genetec vs Verkada), Rhombus comparison, Arcadian AI SOC blog (2025).
