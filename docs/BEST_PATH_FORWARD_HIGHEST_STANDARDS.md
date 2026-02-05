# Best Path Forward — Highest Standards

Single prioritized roadmap to bring Vigil to **best-in-class (90+)** on platform standards and AI log/evidence quality. **100 = full alignment** with NISTIR 8161, SWGDE, CJIS, NIST AI 100-4, and operational best practice.

Additional standards and concepts from **military, civilian, academic, and law enforcement** sources are cataloged in **[RESEARCH_MILITARY_CIVILIAN_ACADEMIC_LE.md](RESEARCH_MILITARY_CIVILIAN_ACADEMIC_LE.md)**; high-priority “missed” items are folded into the phases below. **What the project has integrated and how to keep it applied:** **[STANDARDS_APPLIED.md](STANDARDS_APPLIED.md)**.

---

## Current state vs target

| Area | Current | Target |
|------|---------|--------|
| **Platform (STANDARDS_RATING)** | 85/100 | 90+ |
| **AI log export quality (DATA_COLLECTION_RESEARCH §3.1)** | ~58/100 | 90+ |
| **Security & operations** | 72 | 85+ |
| **Data collection & quality** | 82 | 90+ |

---

## Phase 1 — Foundation (no new code; config & ops)

**Goal:** Maximize value from existing features and harden operations. **Effort: Low. Impact: Medium.**

| # | Action | Outcome |
|---|--------|--------|
| 1.1 | Set **ENABLE_EXTENDED_ATTRIBUTES=1** (and **ENABLE_GAIT_NOTES=1** if desired). | `perceived_gender`, `perceived_age_range`, and related fields populate when a face is detected; log identity score rises. |
| 1.2 | Ensure person/face crop is usable: check resolution and lighting for cameras. | Reduces “Neutral” default when face is too small or dark (see ACCURACY_RESEARCH: 48×48 min, 224×224 for DeepFace). |
| 1.3 | Add **homography** per camera (`config/homography.json`) for sites that need floor-plane mapping. | `world_x`, `world_y` fill; scene/mapping score and heatmaps improve. |
| 1.4 | Configure **loiter zones** and **crossing lines** in camera/site config where behavior analytics matter. | Loiter/line-cross events and threat/anomaly alignment; behavior score rises. |
| 1.5 | In production: set **ENFORCE_HTTPS=1**, run behind TLS-terminating reverse proxy, document in RUNBOOKS. | Security & operations score rises; baseline for CJIS/NIST. |
| 1.6 | Add **pip audit** (or equivalent) to README/CI and schedule dependency updates. | CVE/dependency process in place. |
| 1.7 | **Civilian/DPIA:** When biometric (face/emotion) or LPR is enabled, show reminder or link to DPIA; ensure “What we collect” and lawful-basis summary are in Settings/docs. | GDPR/ICO alignment; RESEARCH_MILITARY_CIVILIAN_ACADEMIC_LE §3. |

**References:** DATA_COLLECTION_RESEARCH.md (§3.1, §5), STANDARDS_RATING.md, CONFIG_AND_OPTIMIZATION.md, MAPPING_OPTIMIZATION_RESEARCH.md, RESEARCH_MILITARY_CIVILIAN_ACADEMIC_LE.md.

---

## Phase 2 — Data quality (accuracy & log richness)

**Goal:** Bring AI log export quality from ~58 to the high 70s–80s. **Effort: Medium. Impact: High.**

| # | Action | Outcome |
|---|--------|--------|
| 2.1 | **Emotion:** Preprocess low-light person crop (CLAHE/gamma) before DeepFace/EmotiEffLib; enforce minimum crop size 48×48 (document 224×224 for age/gender). | Fewer spurious “Neutral”; perceived_gender/age more reliable when face visible. |
| 2.2 | **Pose:** Run MediaPipe on **person crop** (with fallback to full frame); derive Sitting/Walking/Standing from landmarks where feasible. | Richer pose label; aligns with ACCURACY_RESEARCH and DATA_COLLECTION_RESEARCH §3.1. |
| 2.3 | **Threat/behavior:** Centroid smoothing over last K frames; debounce line-cross (require 1–2 cycles on opposite side). Keep threat_score/anomaly_score aligned with events (e.g. loiter → higher anomaly). | Fewer false line-crosses; behavior and threat scores more meaningful. |
| 2.4 | **Height:** If many rows sit at 120 or 220 cm, add per-camera **HEIGHT_REF_CM** / **HEIGHT_REF_PX** (env or config) and document in ACCURACY_RESEARCH_AND_IMPROVEMENTS.md. | Better estimated_height_cm; fewer clamp artifacts. |
| 2.5 | **Audio (if capture_audio is used):** Use best available ASR (e.g. Google/Whisper/Deepgram); fuse acoustic features with text for stress/emotion. | audio_transcription, audio_emotion, audio_stress_level reflect real speech when mic is on. |

**References:** ACCURACY_RESEARCH_AND_IMPROVEMENTS.md, DATA_COLLECTION_RESEARCH.md (§3.1, §4), GAIT_AND_POSE_OPEN_SOURCE.md.

---

## Phase 3 — Security & evidence (platform 90+)

**Goal:** Close the largest gaps in STANDARDS_RATING: encryption at rest, TLS, legal hold. **Effort: Medium–High. Impact: High.**

| # | Action | Outcome |
|---|--------|--------|
| 3.1 | **Encryption at rest:** Implement optional app-level encryption for DB and/or recordings (key from env or KEY_MANAGEMENT.md). | Security & operations score rises; aligns with CJIS/FIPS 140-2 expectations. |
| 3.2 | **TLS enforcement:** ENFORCE_HTTPS=1 already redirects; add explicit “reject non-HTTPS” in production and document in RUNBOOKS and STANDARDS_RATING. | Clear production baseline. |
| 3.3 | **Legal hold workflow:** Formal “hold” flag or workflow for evidence preservation (API + UI); retention and export respect hold. | NIST IR 8387 / SWGDE; closes STANDARDS_RATING gap. |
| 3.4 | **Recording fixity:** If not already enabled, turn on **ENABLE_RECORDING_FIXITY** and ensure fixity job runs; manifest includes fixity status. | OSAC/SWGDE fixity; detect bit rot or tampering. |
| 3.5 | **Export certificate (optional):** Signed manifest or sidecar (e.g. JSON with signature of export hash + metadata) for high-assurance deployments. | SWGDE 23-V-001; optional dual-hash per RESEARCH_IMPROVEMENTS_ACADEMIC_LE. |
| 3.6 | **Evidence collection checklist (SWGDE 18-F-002):** Optional “collection” metadata at recording start or in export manifest: operator, purpose, cameras, retention. | Aligns with 2025 digital evidence collection best practices. |
| 3.7 | **OSAC image taxonomy:** Document in RUNBOOKS that recorded file = primary image; export = working image; fixity job = OSAC-aligned; optional “working image” in manifest. | RESEARCH_MILITARY_CIVILIAN_ACADEMIC_LE §2. |

**References:** STANDARDS_RATING.md, KEY_MANAGEMENT.md, RESEARCH_IMPROVEMENTS_ACADEMIC_LE.md, AI_DETECTION_LOGS_STANDARDS.md, RESEARCH_MILITARY_CIVILIAN_ACADEMIC_LE.md.

---

## Phase 4 — Optional / future (beyond 90)

**Goal:** Stretch goals for full “100” alignment and next-gen features. **Effort: Variable. Impact: Depends on use case.**

| # | Action | Outcome |
|---|--------|--------|
| 4.1 | Per-frame or per-segment **UTC in MP4 export** (timed metadata track). | NISTIR 8161 / ONVIF frame-accurate time in one file. |
| 4.2 | **CADF-style audit export** (initiator, target, outcome) and optional SIEM-friendly format. | Audit & accountability at highest level. |
| 4.3 | **ReID / watchlist:** Replace “Unidentified” with stable individual or face_match_confidence when configured. | Identity & demographics score → 85+. |
| 4.4 | **Cross-camera association** using world_x/world_y and homography (e.g. same identity across cameras). | Single trajectory per person; see MAPPING_OPTIMIZATION_RESEARCH, ENTERPRISE_ROADMAP. |
| 4.5 | **Natural-language search** over events/ai_data (embedding + query). | ENTERPRISE_ROADMAP next-gen AI. |
| 4.6 | **Demographic fairness / FRVT:** Document that perceived_gender/age are not NIST FRVT-validated and may show demographic differentials; optional internal audit or FRVT if face used for identification. | RESEARCH_MILITARY_CIVILIAN_ACADEMIC_LE §2, §4 (Gender Shades). |
| 4.7 | **Video redaction (GDPR/CCPA):** Document in LEGAL_AND_ETHICS that for SAR or third-party sharing, use external redaction tool on exported video; optional future: link or API to redaction. | RESEARCH_MILITARY_CIVILIAN_ACADEMIC_LE §3. |

**References:** RESEARCH_IMPROVEMENTS_ACADEMIC_LE.md, IDENTITY_MARKERS_AND_REID.md, MAPPING_OPTIMIZATION_RESEARCH.md, ENTERPRISE_ROADMAP.md, RESEARCH_MILITARY_CIVILIAN_ACADEMIC_LE.md.

---

## Execution order (recommended)

1. **Phase 1** — Do first; no code change required for 1.1–1.4, minimal for 1.5–1.6. Re-run log export and re-score using DATA_COLLECTION_RESEARCH §3.1.
2. **Phase 2** — Implement in order 2.1 → 2.2 → 2.3 → 2.4; 2.5 if audio is in scope. Re-measure log quality (target: high 70s–low 80s).
3. **Phase 3** — Prioritize 3.1 (encryption) and 3.3 (legal hold) for maximum standards impact; 3.2 and 3.4 are quick. Re-run STANDARDS_RATING; target 90+ overall.
4. **Phase 4** — Per roadmap and resource; not required for “highest standards” 90+.

---

## Summary

| Phase | Focus | Target |
|-------|--------|--------|
| **1** | Config, homography, behavior zones, HTTPS, deps | Log quality +10–15; ops hardened |
| **2** | Emotion/pose/behavior/height/audio accuracy | Log quality 75–85; data collection 90+ |
| **3** | Encryption at rest, legal hold, fixity, TLS | Platform 90+; security 85+ |
| **4** | Per-frame UTC, CADF, ReID, NL search | Stretch to 95+ / 100 |

**Best path:** Complete Phase 1, then Phase 2, then Phase 3. Phase 4 when pursuing maximum alignment or next-gen features.

**Implementation status:** Many Phase 1–3 and several Phase 4 items are implemented (legal hold, fixity, HTTPS reject, OSAC image_type, DPIA/redaction docs, emotion CLAHE, scene variance, centroid smoothing, 224×224 age/gender, threat/event alignment, FRVT disclaimer, and more). See **[STANDARDS_APPLIED.md](STANDARDS_APPLIED.md)** for the full list and **[PLAN_90_PLUS_DATA_POINTS.md](PLAN_90_PLUS_DATA_POINTS.md)** for the data-quality roadmap.

---

## References

- **STANDARDS_RATING.md** — Overall 85/100 and category scores.
- **DATA_COLLECTION_RESEARCH.md** — Log export score (§3.1), config (§5), next steps (§4).
- **ACCURACY_RESEARCH_AND_IMPROVEMENTS.md** — Per-field sources and improvements.
- **AI_DETECTION_LOGS_STANDARDS.md** — NISTIR 8161, SWGDE alignment.
- **RESEARCH_IMPROVEMENTS_ACADEMIC_LE.md** — Export, fixity, legal hold, CADF, signing.
- **ENTERPRISE_ROADMAP.md** — Scale-out and next-gen AI.
- **KEY_MANAGEMENT.md** — Encryption and signing keys.
- **RESEARCH_MILITARY_CIVILIAN_ACADEMIC_LE.md** — Military, civilian, academic, and LE sources; missed areas and P1–P3 actions.
