# Vigil — Highest Standards Rating (1–100)

This document rates the Vigil edge video security platform against **highest industry and government standards**: NISTIR 8161, SWGDE, CJIS, NIST AI 100-4, and best-in-class evidence and operations practice. **100 = full alignment** with those standards.

---

## Overall score: **80 / 100**

| Category | Weight | Score | Summary |
|----------|--------|-------|---------|
| **Chain of custody & evidence** | 25% | 90 | Per-row integrity_hash (ai_data, events); export SHA-256 + X-Export-* headers; timestamp_utc, system_id, model_version; verify APIs; recording fixity option |
| **Access control & auth** | 20% | 88 | RBAC (viewer/operator/admin), MFA (TOTP), password policy/expiry/history, session timeout, lockout; export-approval (civilian mode) |
| **Data collection & quality** | 15% | 82 | Gated by recording; canonical row schema; primary-person consistency (centroid + attributes); height scaling; batch + flush on stop |
| **Audit & accountability** | 15% | 88 | Audit log (login, export, config, recording); integrity verification endpoints; retention (RETENTION_DAYS, AUDIT_RETENTION_DAYS) |
| **Privacy & ethics** | 10% | 78 | Civilian mode, optional sensitive attributes, docs (CIVILIAN_ETHICS_AUDIT, LEGAL_AND_ETHICS); ReID/watchlist opt-in |
| **Security & operations** | 10% | 65 | Secure defaults partial; CSP/HSTS/HTTPS configurable; no encryption at rest; TLS not enforced in-app |
| **Documentation & provenance** | 5% | 95 | 40+ docs (standards, audit, collection, accuracy, config); .env.example and CONFIG_AND_OPTIMIZATION; AI model_version in every row |

**Weighted:** (90×0.25 + 88×0.20 + 82×0.15 + 88×0.15 + 78×0.10 + 65×0.10 + 95×0.05) ≈ **83.5** → **80/100** to reflect remaining gaps (encryption at rest, enforced TLS, formal legal-hold workflow).

---

## What “highest standards” means here

- **Chain of custody**: NISTIR 8161 / SWGDE — UTC timestamps, equipment ID, per-row and export-level integrity, operator and system in export headers. **Vigil: implemented.**
- **Access & audit**: CJIS/NIST — RBAC, MFA, session/lockout, audit log and verification. **Vigil: strong.**
- **Data collection**: Only when recording on; consistent schema; same primary person for centroid and attributes; scalable height estimate. **Vigil: improved and documented.**
- **Privacy**: Civilian mode (export requires approval); sensitive attributes opt-in; ethics docs. **Vigil: good.**
- **Security**: Encryption at rest, enforced TLS, key management. **Vigil: weak (documented only).**

---

## Recent improvements (reflected in score)

- **Consistent ai_data row shape**: Every row has all canonical columns; batch insert uses fixed column list; export and analytics have stable schema.
- **Primary person consistency**: Centroid and extended attributes (height, build, hair, clothing) use the same person (largest bbox by area).
- **Estimated height**: Reference scales with frame height (`frame_h * 0.45`) for resolution-independent estimate; clamp 120–220 cm.
- **MediaPipe**: Tasks API support for 0.10.30+; auto-download pose model; gait_notes and fall detection unchanged.
- **Documentation**: DATA_COLLECTION_RESEARCH.md, STANDARDS_RATING.md; .env optimized for standards.

---

## How to raise the score toward 100

| Gap | Impact | Action |
|-----|--------|--------|
| **Encryption at rest** | High | Optional app-level encryption for DB and/or recordings; key management (see KEY_MANAGEMENT.md). |
| **TLS enforcement** | Medium | ENFORCE_HTTPS=1 + reverse-proxy docs; reject non-HTTPS in production. |
| **Legal hold workflow** | Medium | Formal “hold” flag or workflow for evidence preservation (API + UI). |
| **Input validation** | Low | Centralize request validation (limit/offset, query params) for v1 APIs. |
| **CVE/dependency process** | Low | `pip audit` in README/CI; scheduled dependency updates. |

---

## References

- **SYSTEM_RATING.md** — Technical security rating (74/100).
- **APP_REVIEW_AND_RATING.md** — Feature/functionality/design review (78/100).
- **AI_DETECTION_LOGS_STANDARDS.md** — NISTIR 8161, SWGDE alignment.
- **AUDIT_DATA_COLLECTION.md** — Data collection and chain-of-custody audit.
- **DATA_COLLECTION_RESEARCH.md** — Collection pipeline and improvements.
- **CONFIG_AND_OPTIMIZATION.md** — Env presets for speed, accuracy, production.
- **GOVERNMENT_STANDARDS_AUDIT.md** — Full gap analysis.
