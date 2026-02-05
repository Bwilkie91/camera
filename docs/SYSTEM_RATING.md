# System Rating (1–100 vs Best-in-Class)

Vigil is scored against **government and best-in-class standards** (NIST, CJIS, ISO 27001, NISTIR 8161). **100 = full alignment** with those standards; the score reflects current gaps and strengths.

---

## Overall Score: **74 / 100**

| Category | Weight | Score | Notes |
|----------|--------|-------|--------|
| Access Control & Auth | 20% | 92 | RBAC, optional MFA, password policy/expiry/history, session timeout, lockout |
| Audit & Accountability | 25% | 88 | Auth/config/export/recording events, per-row integrity_hash, /audit_log/verify, SHA-256 export |
| Data Protection & Encryption | 20% | 30 | No app-level encryption at rest; TLS documented, not enforced |
| Video Export & Chain of Custody | 15% | 82 | NISTIR 8161-style metadata, X-Export-SHA256, ?format=mp4 when ffmpeg available |
| Operational Security | 10% | 78 | Secure defaults partial; headers (CSP/HSTS) configurable; input caps in place |
| Retention & Compliance | 10% | 75 | RETENTION_DAYS, AUDIT_RETENTION_DAYS; legal hold not formalized |

**Best-in-class (100)** would add: encryption at rest (FIPS/key management), enforced TLS, formal CVE/dependency process, legal hold workflow, and full input validation schema.

---

## What “Best in Class” Means Here

- **Access & Auth**: Role- and resource-scoped access (CJIS/NIST), MFA, strong password and session controls → **current: strong**.
- **Audit**: Immutable, integrity-verified logs; export with hashes → **current: strong**.
- **Data protection**: Encryption at rest and in transit, key lifecycle → **current: weak** (documented only).
- **Evidence export**: Standard metadata, integrity, chain of custody → **current: good**.
- **Operations**: No default secrets in prod, headers, validation, dependency hygiene → **current: partial**.

---

## Improvements Applied (This Pass)

- **Startup**: Warn when `FLASK_SECRET_KEY` is default; log camera mode (auto vs env) and listen port.
- **Run script**: `run.sh` uses `.venv` if present and respects `PORT`.
- **Config**: `.env.example` recommends `CAMERA_SOURCES=auto` for laptop/device auto-detect.

---

## Next Steps to Raise the Score

1. **Encryption at rest** (largest gap): Document or add optional app-level encryption for DB/recordings; key management guidance.
2. **TLS enforcement**: Option to reject non-HTTPS in production (ENFORCE_HTTPS already exists; ensure reverse-proxy docs).
3. **Dependency/CVE process**: Add `pip audit` or similar to README/CI; schedule updates.
4. **Input validation**: Centralize request validation (e.g. limit/offset) for v1 APIs.
5. **Legal hold**: Optional “hold” flag or workflow for evidence preservation.

See **GOVERNMENT_STANDARDS_AUDIT.md** for full gap analysis and **ENTERPRISE_ROADMAP.md** for roadmap.
