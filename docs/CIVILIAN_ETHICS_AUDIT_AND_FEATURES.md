# Civilian Use: Ethics Audit & Enterprise Best-in-Class Features

This document (1) **audits** the codebase for capabilities that are **legal in many jurisdictions but ethically sensitive** for civilian deployment, and (2) recommends **enterprise-grade, ethical, best-in-class features** suitable for responsible civilian use. It does not constitute legal advice; laws vary by jurisdiction.

---

## Part 1 — Gray zone: legal but ethically sensitive

The following are **already present** in the system. They are generally legal when used on your own property and with appropriate notice/consent where required, but can be considered invasive or disproportionate for typical home/property use. Best practice: **disable or scope them narrowly** unless you have a clear, documented purpose (e.g. perimeter LPR for theft, not general street capture).

| Capability | Where in codebase | Legal note (summary) | Civilian best practice |
|------------|-------------------|----------------------|-------------------------|
| **Facial / emotion analysis** | `app.py`: DeepFace, EmotiEffLib; `_get_dominant_emotion`, `_extract_extended_attributes` (age, gender, emotion) | Biometric laws (e.g. BIPA, GDPR Art. 9) may require consent or lawful basis; some states restrict use. | Off by default; enable only where justified; document purpose; avoid storing raw face crops long-term. |
| **License plate recognition (LPR)** | `app.py`: LPR on YOLO vehicle ROIs; `license_plate` in `ai_data` | Generally legal on private property; pointing at public street can raise privacy expectations. | Restrict to private driveways/parking; avoid continuous capture of public road; short retention. |
| **Audio capture + transcription** | `app.py`: PyAudio, SpeechRecognition, `_extract_audio_attributes` (transcription, sentiment, stress, threat, “intoxication” stub) | Many regions require consent for audio (two-party consent in some US states); storing conversations is high risk. | Off by default for civilian; if on: clear signage “audio recorded”; minimal retention; no cloud STT by default. |
| **Wi‑Fi / device presence** | `app.py`: Scapy sniff (MAC, OUI, probe SSIDs); `device_mac` in `ai_data` | Receiving broadcast frames is generally legal; inferring identity or presence can feel intrusive. | Off by default; use only for “device count” or technical diagnostics, not to identify individuals. |
| **ReID (persistent identity)** | `proactive/reid.py`: OSNet/ResNet embeddings; matching by cosine similarity | Embeddings can be treated as biometric data (BIPA, GDPR). | Disabled by default; if enabled: document lawful basis; retention aligned with policy; no export of embeddings. |
| **Stored “individual” / facial_features** | `app.py`: `individual` (“Unidentified”), `facial_features` (pose, emotion) in `ai_data` | Even “Unidentified” plus pose/emotion can support re-identification; treat as personal data where applicable. | Prefer anonymized analytics (counts, zones); limit retention of attributes that support identification. |
| **Notable behavior / threat scores** | `app.py`: `_evaluate_notable_behavior` (stress, emotion, audio threat, loitering); screenshots in `notable_screenshots/` | Legal; can reinforce bias or over-surveillance if thresholds are aggressive. | Use for genuine safety (e.g. trespass, loitering); avoid over-reliance on emotion/stress alone; review thresholds. |

**Summary:** All of the above can be **100% legal** in a given jurisdiction (e.g. on your own property, with notice, and no prohibited use). The “unethical” risk is **disproportionate or non-transparent** use (e.g. recording audio without notice, LPR on public street, emotion tracking without purpose). Recommendation: **default-off for the most invasive options**, with clear env/config and docs so a civilian operator can run a “minimal” or “privacy-preserving” preset.

---

## Part 2 — Enterprise best-in-class features (ethical & legal for civilians)

These are **high-value, ethical, and align with enterprise and government standards** while remaining appropriate for civilian use. They improve security, transparency, compliance, and evidence quality without increasing creepiness.

### 2.1 Transparency & consent

| Feature | Description | Reference / standard |
|---------|-------------|----------------------|
| **Recording / analytics indicator in UI** | Prominent “Recording in progress” and “AI analytics: motion, loitering, …” so anyone using the dashboard sees what’s active. | Transparency (GDPR, ethical VMS). |
| **Privacy / signage reminder** | Optional configurable text (e.g. “Ensure signage is displayed where required”) in Settings or first-run; link to privacy policy URL. | Best practice (docs/LEGAL_AND_ETHICS.md). |
| **“What we collect” summary** | Settings page or docs: one-page summary of what is recorded (video, audio on/off, LPR, face/emotion, WiFi, retention). | Minimization, transparency. |

### 2.2 Purpose limitation & presets

| Feature | Description | Reference / standard |
|---------|-------------|----------------------|
| **Privacy / minimal preset** | Single config or env preset: motion + line-cross + loiter only; no face, no emotion, no audio, no WiFi, no LPR; short retention. | Data minimization (GDPR, NIST). |
| **Feature flags in system status** | `GET /api/v1/system_status` (or equivalent) already surfaces capabilities; extend with clear “audio_capture”, “lpr”, “emotion”, “wifi_sniff”, “reid” so operator can verify what’s on. | Operational transparency. |

### 2.3 Retention, minimization & evidence

| Feature | Description | Reference / standard |
|---------|-------------|----------------------|
| **Retention policy in export metadata** | Export CSV/headers include “Retention policy: X days” and “Export purpose: …” so recipients know the scope. | NISTIR 8161, chain of custody. |
| **Legal hold / preservation** | Ability to “hold” specific events or time ranges from automatic deletion (e.g. for insurance or LE); optional export bundle (video + CSV + manifest). | Legal/compliance (ENTERPRISE_GOV_STANDARDS_IMPROVEMENTS.md gap). |
| **NTP / time sync check in health** | Verify system time vs NTP; report “time_sync_status” in `/health/ready` or system status so evidence timestamps are defensible. | Admissibility, NISTIR 8161. |

### 2.4 Access control & audit (civilian-friendly)

| Feature | Description | Reference / standard |
|---------|-------------|----------------------|
| **“My access history” (viewer)** | Let each user see their own recent logins and exports (read-only view of audit log filtered by user_id). | Transparency, NIST AU-9. |
| **Temporary guest / contractor access** | Time-limited accounts or PIN for viewing (e.g. 24–72 hours) with no export; auto-expire. | Minimize standing access. |
| **Export approval workflow (optional)** | For high-sensitivity deployments: export requires second role (e.g. admin approval) and is logged. | CJIS-style, enterprise. |

### 2.5 Deployment checklist (purpose, necessity, less intrusive options)

When deploying or expanding surveillance (e.g. adding cameras, enabling biometric or LPR):

| Step | Action | Reference |
|------|--------|-----------|
| **Purpose** | Document why you run surveillance (security, safety, etc.) and retain that with your config. | LEGAL_AND_ETHICS § Best practices. |
| **Necessity** | Collect only what is necessary; use minimal or privacy presets where possible. | §2.2 Privacy / minimal preset. |
| **Less intrusive options** | Consider whether less intrusive measures (e.g. motion-only, no face/emotion/LPR) would suffice. | GDPR/EDPB proportionality. |
| **DPIA** | When biometric (face/emotion) or LPR is on, complete a DPIA and document lawful basis. | LEGAL_AND_ETHICS § DPIA and lawful basis; GET /api/v1/what_we_collect (dpia_recommended). |
| **Redaction** | For SAR or third-party sharing, use an external redaction tool on exported video. | LEGAL_AND_ETHICS § Video redaction. |

See **docs/LEGAL_AND_ETHICS.md** and **docs/RESEARCH_MILITARY_CIVILIAN_ACADEMIC_LE.md** §3.

### 2.6 Operational & security hardening

| Feature | Description | Reference / standard |
|---------|-------------|----------------------|
| **Encryption at rest** | Encrypt SQLite and recording storage (LUKS or app-level with key from env/vault); document in README. | FIPS 140-2, ISO 27001 (ENTERPRISE_GOV_STANDARDS_IMPROVEMENTS.md). |
| **Dependency / CVE scanning** | `pip-audit` or `safety` in CI; schedule updates; document in INSTALL_AUDIT. | Vulnerability management (SURVEILLANCE_COMMAND_COMPETITORS_AND_RATING.md). |
| **Saved searches + audit** | Save filter presets (e.g. “Front door, last 7 days”); log search/saved-search use in audit log. | NIST AU-9, SOC best practice. |

### 2.7 Civilian-specific UX & compliance

| Feature | Description | Reference / standard |
|---------|-------------|----------------------|
| **Incident export bundle** | One-click: export a time range as “Incident pack” (video clips + AI/events CSV + manifest + checksums) for insurance or LE, with chain-of-custody headers. | NISTIR 8161, civilian evidence. |
| **Home / away mode** | Preset: “Away” = full analytics + alerts; “Home” = motion-only or disable recording in sensitive zones (e.g. indoor). | Minimization, proportionality. |
| **Clear “disable” for each sensitive capability** | Env or UI: explicitly disable audio, LPR, emotion, WiFi, ReID so the operator can run a minimal stack. | LEGAL_AND_ETHICS.md, minimization. |

---

## Part 3 — Implementation priority (civilian focus)

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| P0 | Privacy/minimal preset (disable face, emotion, audio, WiFi, LPR by config) | Low | High (avoids misuse; legal safety) |
| P0 | Recording + analytics indicator in UI | Low | High (transparency) |
| P1 | “What we collect” summary (Settings or docs) | Low | Medium |
| P1 | NTP/time sync in health or system status | Low | Medium (evidence) |
| P1 | Legal hold + incident export bundle | Medium | High (compliance, civilian use) |
| P2 | My access history (own audit view) | Medium | Medium |
| P2 | Encryption at rest (doc + optional implementation) | Medium | High |
| P2 | Dependency scanning in CI | Low | Medium |
| P3 | Temporary guest access; saved searches + audit | Medium | Medium |

---

## Part 4 — References

- **docs/LEGAL_AND_ETHICS.md** — Recording, biometrics, deterrence, retention.
- **docs/ENTERPRISE_ROADMAP.md** — Best-in-class comparison, scalability, AI extension points.
- **docs/ENTERPRISE_GOV_STANDARDS_IMPROVEMENTS.md** — NIST/CJIS/ISO improvements and gaps.
- **docs/SURVEILLANCE_COMMAND_COMPETITORS_AND_RATING.md** — Competitor features and must-add list.
- **docs/GOVERNMENT_STANDARDS_AUDIT.md** — Gap analysis and ratings.

---

## Summary

- **Gray zone:** The system already includes face/emotion, LPR, audio (transcription/sentiment), WiFi presence, and ReID. All can be legal; risk is **overuse or lack of transparency**. Default-off or scoped use plus documentation is the ethical approach.
- **Best-in-class for civilians:** Focus on **transparency** (indicators, “what we collect”), **minimization** (privacy preset, feature toggles), **evidence quality** (time sync, legal hold, incident bundle), **access control** (my access history, temporary access), and **security** (encryption at rest, CVE scanning). These match enterprise and government standards while keeping the system appropriate for responsible civilian use.

---

## Implemented (this codebase)

| Feature | Location |
|--------|----------|
| Privacy / minimal preset | Config `privacy_preset`; Recording config `ai_detail` = minimal disables emotion/LPR; Settings → Privacy preset |
| Feature flags in system status | `GET /api/v1/system_status` → `feature_flags`, `privacy_preset`, `home_away_mode` |
| Recording + analytics indicator | Dashboard banner when recording |
| What we collect summary | `GET /api/v1/what_we_collect`; Settings → Privacy & transparency |
| Privacy / signage reminder + policy URL | Config keys; Settings (admin) |
| Retention in export metadata | `X-Retention-Policy-Days` on export_data and recording export |
| NTP / time sync in health | `GET /health/ready` → `time_sync_status` (optional ntplib) |
| Legal hold | Existing `/api/v1/legal_hold`; retention job excludes held items |
| Incident export bundle | `GET /api/v1/export/incident_bundle`; Export page section |
| My access history | `GET /audit_log?mine=1`; Settings for non-admin |
| Saved searches + audit | `saved_searches` table; `/api/v1/saved_searches` |
| Temporary guest access | `users.expires_at`; login rejected when past |
| Export requires approval | Env `EXPORT_REQUIRES_APPROVAL=1` |
| Home / away mode | Config `home_away_mode`; system_status |
| Export data date range | `/export_data?date_from=&date_to=` |

**See also:** [RESEARCH_MILITARY_CIVILIAN_ACADEMIC_LE.md](RESEARCH_MILITARY_CIVILIAN_ACADEMIC_LE.md) — DPIA triggers, lawful basis, video redaction for SAR/third-party sharing, and “less intrusive alternatives” checklist from civilian/LE sources.
