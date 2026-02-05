# Vigil — Highest Standards Rating (1–100)

This document rates the Vigil edge video security platform against **highest industry and government standards**: NISTIR 8161, SWGDE, CJIS, NIST AI 100-4, and best-in-class evidence and operations practice. **100 = full alignment** with those standards.

---

## Overall score: **85 / 100**

| Category | Weight | Score | Summary |
|----------|--------|-------|---------|
| **Chain of custody & evidence** | 25% | 90 | Per-row integrity_hash (ai_data, events); export SHA-256 + X-Export-* headers; timestamp_utc, system_id, model_version; verify APIs; recording fixity option |
| **Access control & auth** | 20% | 88 | RBAC (viewer/operator/admin), MFA (TOTP), password policy/expiry/history, session timeout, lockout; export-approval (civilian mode) |
| **Data collection & quality** | 15% | 82 | Gated by recording; canonical row schema; primary-person consistency (centroid + attributes); height scaling; batch + flush on stop |
| **Audit & accountability** | 15% | 88 | Audit log (login, export, config, recording); integrity verification endpoints; retention (RETENTION_DAYS, AUDIT_RETENTION_DAYS) |
| **Privacy & ethics** | 10% | 78 | Civilian mode, optional sensitive attributes, docs (CIVILIAN_ETHICS_AUDIT, LEGAL_AND_ETHICS); ReID/watchlist opt-in |
| **Security & operations** | 10% | 72 | ENFORCE_HTTPS=1 (redirect) or =reject (403); CSP/HSTS configurable; fixity option; no encryption at rest |
| **Documentation & provenance** | 5% | 95 | 40+ docs (standards, audit, collection, accuracy, config); .env.example and CONFIG_AND_OPTIMIZATION; AI model_version in every row |

**Weighted:** (90×0.25 + 88×0.20 + 82×0.15 + 88×0.15 + 78×0.10 + 72×0.10 + 95×0.05) ≈ **85** → **85/100** (remaining gap: encryption at rest; TLS and legal hold implemented via ENFORCE_HTTPS and /api/v1/legal_hold).

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
- **Estimated height**: Reference scales with frame height; optional HEIGHT_REF_CM / HEIGHT_REF_PX per camera; clamp 120–220 cm.
- **MediaPipe**: Person crop first; Standing/Sitting/Walking from landmarks; gait_notes and fall detection.
- **Emotion**: CLAHE on L channel when dark (EMOTION_CLAHE_THRESHOLD); min crop 48×48; 224×224 for DeepFace age/gender.
- **Scene**: Lower-half mean + variance (SCENE_VAR_MAX_INDOOR); Indoor only when mean &lt; 100 and var &lt; threshold.
- **Motion**: Optional MOG2 backend + MOTION_THRESHOLD + MOTION_MOG2_VAR_THRESHOLD; morphology.
- **Loiter/line**: Centroid smoothing (CENTROID_SMOOTHING_FRAMES); line-cross debounce; threat_score +10 for line_cross.
- **Legal hold**: GET/POST/DELETE /api/v1/legal_hold; retention excludes held items; RUNBOOKS.
- **HTTPS**: ENFORCE_HTTPS=1 (redirect) or =reject (403); RUNBOOKS § Evidence and export.
- **OSAC image_type**: Recording manifest = primary; incident_bundle = working; RUNBOOKS.
- **DPIA / redaction**: LEGAL_AND_ETHICS § DPIA and § Video redaction; what_we_collect face_attributes_note (FRVT).
- **Documentation**: STANDARDS_APPLIED.md, PLAN_90_PLUS_DATA_POINTS.md, DATA_POINT_ACCURACY_RATING.md; .env highest-standards block.

---

## How to raise the score toward 100

**Prioritized path:** See **[BEST_PATH_FORWARD_HIGHEST_STANDARDS.md](BEST_PATH_FORWARD_HIGHEST_STANDARDS.md)** for a phased roadmap (config → data quality → security & evidence → optional). **Current status:** Many Phase 1–3 items are done — see **[STANDARDS_APPLIED.md](STANDARDS_APPLIED.md)** and **[PLAN_90_PLUS_DATA_POINTS.md](PLAN_90_PLUS_DATA_POINTS.md)**.

| Gap | Impact | Action / status |
|-----|--------|-----------------|
| **Encryption at rest** | High | Documented (LUKS/vault in KEY_MANAGEMENT, RUNBOOKS). Optional app-level encryption still pending. |
| **TLS enforcement** | Medium | **Done:** ENFORCE_HTTPS=1 (redirect) or =reject (403); RUNBOOKS § Evidence and export. |
| **Legal hold workflow** | Medium | **Done:** GET/POST/DELETE /api/v1/legal_hold; retention excludes held; RUNBOOKS § Legal hold. |
| **Input validation** | Low | Centralize request validation (limit/offset, query params) for v1 APIs. |
| **CVE/dependency process** | Low | **Done:** README § Operations and scripts/audit-deps.sh; pip audit recommended. |

---

## References

- **SYSTEM_RATING.md** — Technical security rating (74/100).
- **APP_REVIEW_AND_RATING.md** — Feature/functionality/design review (78/100).
- **AI_DETECTION_LOGS_STANDARDS.md** — NISTIR 8161, SWGDE alignment.
- **AUDIT_DATA_COLLECTION.md** — Data collection and chain-of-custody audit.
- **DATA_COLLECTION_RESEARCH.md** — Collection pipeline and improvements.
- **CONFIG_AND_OPTIMIZATION.md** — Env presets for speed, accuracy, production.
- **GOVERNMENT_STANDARDS_AUDIT.md** — Full gap analysis.
- **BEST_PATH_FORWARD_HIGHEST_STANDARDS.md** — Prioritized roadmap to 90+ (config, data quality, security, evidence).
- **STANDARDS_APPLIED.md** — What is integrated and how to keep it applied.
- **PLAN_90_PLUS_DATA_POINTS.md** — Per–data-point plan to 90+ with enterprise/LE/journal refs.
