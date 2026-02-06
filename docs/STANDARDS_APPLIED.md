# Standards Applied — Project Commitment

This document states what the Vigil project **has integrated** from the best path to highest standards and how we **apply it going forward**. It is the single place to check “what’s in force” and how to keep the project aligned.

---

## 1. Commitment

The project applies the roadmap in **[BEST_PATH_FORWARD_HIGHEST_STANDARDS.md](BEST_PATH_FORWARD_HIGHEST_STANDARDS.md)** and the additional sources in **[RESEARCH_MILITARY_CIVILIAN_ACADEMIC_LE.md](RESEARCH_MILITARY_CIVILIAN_ACADEMIC_LE.md)**. All changes that touch evidence, export, collection, privacy, or security should:

- Preserve or strengthen chain of custody (integrity_hash, timestamp_utc, system_id, model_version, export SHA-256).
- Respect the phased plan: Foundation → Data quality → Security & evidence → Optional.
- Not remove or weaken DPIA/redaction/collection-checklist or OSAC/fixity documentation.

---

## 2. What is integrated (current)

| Area | Integrated | Where |
|------|------------|--------|
| **Roadmap as default** | Best path phases 1–4 and research P1–P3 are the default plan. | BEST_PATH_FORWARD_HIGHEST_STANDARDS.md; RESEARCH_MILITARY_CIVILIAN_ACADEMIC_LE.md. |
| **Cursor rule** | AI and contributors are instructed to follow the best path and research doc when changing evidence/export/privacy/security. | .cursor/rules/standards-best-path.mdc (always apply). |
| **Env “highest standards”** | Recommended production/evidence preset in .env.example (EXTENDED_ATTRIBUTES, ENFORCE_HTTPS, fixity, DPIA/redaction note). | .env.example “Highest standards” block. |
| **Evidence collection checklist** | Incident bundle manifest includes a collection_checklist (operator, purpose, cameras, retention_policy) per SWGDE 18-F-002. | app.py: incident_bundle response. |
| **DPIA / “What we collect”** | GET /api/v1/what_we_collect returns dpia_recommended and docs_privacy when biometric or LPR is on. | app.py: api_v1_what_we_collect. |
| **OSAC / production runbook** | RUNBOOKS describe primary/working image, fixity, and production HTTPS. | docs/RUNBOOKS.md § Evidence and export. |
| **Dependency audit** | README instructs to run pip audit (or equivalent) for CVE/dependency process. | README.md § Operations. |
| **Cross-references** | STANDARDS_RATING, DATA_COLLECTION_RESEARCH, CIVILIAN_ETHICS, GOVERNMENT_STANDARDS_AUDIT link to best path and research. | Those docs. |
| **Current ratings** | STANDARDS_RATING 85/100; GOVERNMENT_STANDARDS_AUDIT 75/100; log export baseline ~58 (DATA_COLLECTION_RESEARCH §3.1) with applied improvements raising effective score. | docs/STANDARDS_RATING.md; docs/GOVERNMENT_STANDARDS_AUDIT.md; docs/DATA_COLLECTION_RESEARCH.md. |
| **Height calibration** | Optional HEIGHT_REF_CM / HEIGHT_REF_PX for estimated_height_cm (Phase 2.4). | .env.example; app.py _extract_extended_attributes. |
| **HEIGHT_MIN_PX** | Min person bbox height (px) to compute estimated_height_cm (default 60); reduces 120 cm outliers (DATA_QUALITY_IMPROVEMENTS_RESEARCH). | .env.example; app.py _extract_extended_attributes. |
| **detection_confidence** | YOLO confidence for primary person stored per row; export and verify (NIST AI 100-4 provenance). | app.py _extract_extended_attributes; ai_data schema; GET /api/v1/ai_data/verify. |
| **Emotion min crop** | EMOTION_MIN_CROP_SIZE (default 48); skip/Neutral when person crop too small (Phase 2.1). | .env.example; app.py _get_dominant_emotion. |
| **Line-cross debounce** | LINE_CROSS_DEBOUNCE_CYCLES (default 1); confirm centroid on opposite side before firing (Phase 2.3). | .env.example; app.py check_loiter_and_line_cross. |
| **Pose on person crop** | MediaPipe runs on largest person crop first; Standing/Sitting/Walking from landmarks (Phase 2.2). | app.py: _pose_label_from_landmarks, pose block; POSE_MIN_CROP_SIZE. |
| **Audio stress fusion** | energy_db fuses into audio_stress_level when loud (Phase 2.5). | app.py: _extract_audio_attributes. |
| **Legal hold workflow** | GET/POST/DELETE /api/v1/legal_hold; retention excludes held; runbook (Phase 3.3). | app.py; docs/RUNBOOKS.md § Legal hold workflow. |
| **Encryption at rest (doc)** | Phase 3.1: volume-level (LUKS/BitLocker/cloud) in KEY_MANAGEMENT + RUNBOOKS; app-level future. | docs/KEY_MANAGEMENT.md; docs/RUNBOOKS.md § Encryption at rest. |
| **Scene (lower-half mean)** | Indoor/Outdoor from lower-half mean (DATA_POINT_ACCURACY_RATING; IEEE/Sciencedirect). | app.py. |
| **LPR upscale 80 px** | ROI upscaled when &lt; 80×24 px before OCR (DATA_POINT_ACCURACY_RATING). | app.py _lpr_preprocess. |
| **Motion MOG2 + threshold** | MOTION_BACKEND=mog2; MOTION_THRESHOLD env (DATA_POINT_ACCURACY_RATING; IEEE). | app.py detect_motion; .env.example. |
| **90+ plan** | PLAN_90_PLUS_DATA_POINTS.md: phased plan to 90+ with enterprise/LE/journal refs. | docs/PLAN_90_PLUS_DATA_POINTS.md. |
| **224×224 age/gender** | DeepFace crop resized to 224×224 for age/gender path (NIST FRVT, ISO 30137-1). | app.py _extract_extended_attributes. |
| **Centroid smoothing** | CENTROID_SMOOTHING_FRAMES (default 5); moving avg of primary centroid for line-cross (IEEE/Springer). | app.py check_loiter_and_line_cross; .env.example. |
| **MOG2 varThreshold** | MOTION_MOG2_VAR_THRESHOLD (4–64, default 16) for scene tuning. | app.py detect_motion; .env.example. |
| **Recording fixity (Phase 3.4)** | ENABLE_RECORDING_FIXITY=1; fixity job; manifest fixity_stored_sha256, fixity_checked_at, fixity_match (OSAC/SWGDE). | app.py fixity_job, manifest; RUNBOOKS § Evidence and export. |
| **Emotion CLAHE (Phase 2.1)** | EMOTION_CLAHE_THRESHOLD (default 80); CLAHE on L channel when mean intensity low (PLAN_90_PLUS Phase B). | app.py _preprocess_low_light_emotion, _get_dominant_emotion; .env.example. |
| **Scene variance (PLAN_90_PLUS)** | SCENE_VAR_MAX_INDOOR (default 5000); Indoor only when lower-half mean &lt; 100 and var &lt; threshold. | app.py scene block; .env.example. |
| **HTTPS reject (Phase 3.2)** | ENFORCE_HTTPS=reject returns 403 for non-HTTPS (no redirect). | app.py _before_request; RUNBOOKS § Evidence and export. |
| **FRVT disclaimer (Phase 4.6)** | GET /api/v1/what_we_collect returns face_attributes_note when DPIA + extended attributes on (NISTIR 8429). | app.py api_v1_what_we_collect. |
| **Threat score + Line Crossing (Phase 2.3)** | threat_score += 10 for Line Crossing Detected (aligned with loiter/fall). | app.py _extract_extended_attributes. |
| **OSAC image_type (Phase 3.7)** | Recording manifest: image_type 'primary'; incident_bundle manifest: image_type 'working'. | app.py recording_manifest, api_v1_incident_bundle; RUNBOOKS § Evidence. |
| **Audio keywords (PLAN_90_PLUS Phase C)** | Expanded _AUDIO_THREAT_KEYWORDS (intruder, danger, 911, intrusion, etc.) and _AUDIO_STRESS_KEYWORDS (worried, urgent, pain, fall, fell, down). | app.py _extract_audio_attributes. |
| **Export certificate (Phase 3.5 doc)** | KEY_MANAGEMENT § Export manifest signing; RUNBOOKS § Export certificate (optional). SHA-256 in place; signed manifest / dual-hash documented as optional future. | docs/KEY_MANAGEMENT.md; docs/RUNBOOKS.md. |
| **Video redaction (Phase 4.7)** | LEGAL_AND_ETHICS § Video redaction: for SAR/third-party sharing use external redaction tool on exported video; primary vs working copy. | docs/LEGAL_AND_ETHICS.md. |
| **API limit/date validation** | Centralized _api_limit(default, max_cap) and _parse_date_yyyymmdd() for safe limit/date parsing on v1/search, notable_screenshots, audit_log, audit_log/export (NIST/OWASP input validation). | app.py _api_limit, _parse_date_yyyymmdd; SURVEILLANCE_COMMAND_COMPETITORS_AND_RATING § Must-Add. |
| **Competitor & standards 2026** | COMPETITORS_AND_STANDARDS_2026: Rhombus/Verkada AI search (sub-second, NL), ONVIF/NISTIR 8161 alignment, gunicorn/pip-audit/structlog in optional deps. | docs/COMPETITORS_AND_STANDARDS_2026.md; requirements-optional.txt. |
| **DPIA / lawful basis (Phase 1.7)** | LEGAL_AND_ETHICS § DPIA and lawful basis; what_we_collect + dpia_recommended when biometric/LPR on. | docs/LEGAL_AND_ETHICS.md; app.py api_v1_what_we_collect. |
| **Deployment checklist (P3)** | CIVILIAN_ETHICS §2.5: purpose, necessity, less intrusive options, DPIA, redaction (link to LEGAL_AND_ETHICS). | docs/CIVILIAN_ETHICS_AUDIT_AND_FEATURES.md. |
| **Gov/LE alignment notes** | GOVERNMENT_STANDARDS_AUDIT: retention + legal hold Done; ISO 62676, SWGDE 18-F-002, OSAC alignment noted. | docs/GOVERNMENT_STANDARDS_AUDIT.md. |
| **FRVT/demographic in accuracy doc** | ACCURACY_RESEARCH_AND_IMPROVEMENTS: Demographic fairness §; perceived_gender/age not FRVT-validated; face_attributes_note. | docs/ACCURACY_RESEARCH_AND_IMPROVEMENTS.md. |
| **Skip to main content (WCAG 2.4.1)** | React: skip link (visible on focus) + `id="main"`; legacy: skip link + `id="main"`; Dash: skip link + `id="main-content"`. | frontend/src/App.tsx; templates/index.html; dashboard/app.py. |
| **Focus return on modal close (React)** | Help and Quick search modals return focus to trigger button on close (WCAG 2.1.2). | frontend/src/App.tsx. |

---

## 3. How to keep it applied

- **Before changing export or recording logic:** Ensure manifest/export still include operator, system_id, UTC, and integrity (SHA-256); incident_bundle keeps preservation_checklist and collection_checklist.
- **Before adding or changing biometric/LPR:** Check CIVILIAN_ETHICS and RESEARCH_MILITARY_CIVILIAN_ACADEMIC_LE; keep DPIA reminder and “What we collect” accurate.
- **Before changing retention or legal hold:** Ensure retention-by-purpose and hold behavior are documented and not weakened.
- **Re-scoring:** After major changes to data collection or export, re-run the log export score (DATA_COLLECTION_RESEARCH §3.1) and STANDARDS_RATING and update this table if new items are integrated.

---

## 4. Next steps to continue

Implement these next to move toward 90+ (see BEST_PATH_FORWARD phases):

| Priority | Item | Phase | Notes |
|----------|------|--------|--------|
| **P1** | Emotion: preprocess low-light crop (CLAHE/gamma); min face crop 48×48 (224×224 for age/gender) | 2.1 | **Done:** EMOTION_MIN_CROP_SIZE (default 48); 224×224 for age/gender; **CLAHE on L channel** when mean &lt; EMOTION_CLAHE_THRESHOLD (default 80). |
| **P1** | Pose: run MediaPipe on person crop; derive Sitting/Walking/Standing from landmarks | 2.2 | **Done:** Person crop preferred (POSE_MIN_CROP_SIZE 48); _pose_label_from_landmarks returns Standing/Sitting/Walking; person down still overrides. |
| **P1** | Threat/behavior: centroid smoothing; debounce line-cross; align threat_score with events | 2.3 | **Done:** Line-cross debounce (LINE_CROSS_DEBOUNCE_CYCLES, default 1); require centroid on opposite side for N cycles before firing. |
| **P2** | Height calibration: per-camera HEIGHT_REF_CM / HEIGHT_REF_PX | 2.4 | **Done:** env vars in .env.example; app.py uses them when set. |
| **P2** | Audio: better ASR + fuse acoustic features for stress (when capture_audio used) | 2.5 | **Done (fusion):** energy_db fuses into audio_stress_level (loud → boost; no transcription but loud → medium). Better ASR remains config (Google/Whisper/Deepgram). |
| **P3** | Encryption at rest for DB and/or recordings | 3.1 | **Documented:** KEY_MANAGEMENT.md § Encryption at rest (Phase 3.1); RUNBOOKS § Encryption at rest (LUKS/BitLocker/cloud). App-level optional future. |
| **P3** | Legal hold: formal API + UI workflow (hold flag, retention/export respect) | 3.3 | **Done:** GET/POST/DELETE /api/v1/legal_hold; retention excludes held; documented in RUNBOOKS § Legal hold workflow. UI can call APIs. |
| **P3** | Recording fixity (ENABLE_RECORDING_FIXITY; manifest fixity fields) | 3.4 | **Done:** fixity job; manifest includes fixity_stored_sha256, fixity_checked_at, fixity_match. RUNBOOKS § Evidence and export. |
| **P3** | TLS: explicit reject non-HTTPS in production | 3.2 | **Done:** ENFORCE_HTTPS=reject returns 403; ENFORCE_HTTPS=1 redirects. RUNBOOKS updated. |
| **P4** | Demographic/FRVT note when face attributes on | 4.6 | **Done:** GET /api/v1/what_we_collect returns face_attributes_note (NISTIR 8429) when DPIA + extended attributes on. |
| **P3** | OSAC image taxonomy in manifest | 3.7 | **Done:** recording manifest = image_type 'primary'; incident_bundle = image_type 'working'. RUNBOOKS § Evidence and export. |
| **P3** | Export certificate (optional signed manifest) | 3.5 | **Documented:** KEY_MANAGEMENT § Export manifest signing; RUNBOOKS § Export certificate (optional). SHA-256 in place; signed manifest/dual-hash as optional future. |
| **P4** | Video redaction (GDPR/CCPA doc) | 4.7 | **Done:** LEGAL_AND_ETHICS § Video redaction (SAR, third-party; use external redaction tool; primary vs working). |
| **P1** | DPIA reminder when biometric/LPR on | 1.7 | **Done:** LEGAL_AND_ETHICS § DPIA and lawful basis; what_we_collect + dpia_recommended; .env.example. |

Re-score log export (DATA_COLLECTION_RESEARCH §3.1) and STANDARDS_RATING after implementing P1/P3 items.

**Remaining (optional / future):** Per-frame UTC in MP4 export (Phase 4.1; NISTIR 8161); app-level encryption for DB/recordings (Phase 3.1); optional LPRNet or dedicated LPR for 90%+ (PLAN_90_PLUS); signed export manifest (Phase 3.5); CADF-style audit export (Phase 4.2). See **BEST_PATH_FORWARD_HIGHEST_STANDARDS.md** Phase 4 and **PLAN_90_PLUS_DATA_POINTS.md**.

---

## 5. References

- **BEST_PATH_FORWARD_HIGHEST_STANDARDS.md** — Phased roadmap.
- **RESEARCH_MILITARY_CIVILIAN_ACADEMIC_LE.md** — Military, civilian, academic, LE sources and P1–P3 actions.
- **STANDARDS_RATING.md** — Current 85/100 and category scores.
- **AI_DETECTION_LOGS_STANDARDS.md** — NISTIR 8161, SWGDE alignment.
- **CIVILIAN_ETHICS_AUDIT_AND_FEATURES.md** — Transparency, presets, DPIA/redaction.
- **DATA_POINT_ACCURACY_RATING.md** — Per–data-point accuracy rating (1–100) and improvements (military, LE, academic).
- **PLAN_90_PLUS_DATA_POINTS.md** — Plan to bring each data point to 90+ with enterprise/journal research and phased implementation.
