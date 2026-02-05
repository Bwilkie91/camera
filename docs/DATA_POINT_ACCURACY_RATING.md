# Per–Data-Point Accuracy Rating (1–100) — Enterprise Highest Level

This document rates **each collected data point** in the Vigil pipeline **1–100** (100 = best-in-class accuracy for enterprise/military/LE use) and suggests improvements backed by **military, law enforcement, and academic** sources. It complements **ACCURACY_RESEARCH_AND_IMPROVEMENTS.md** and **DATA_COLLECTION_RESEARCH.md**.

---

## Executive summary

| Category | Avg score | Applied in code | Next actions |
|----------|-----------|-----------------|--------------|
| Provenance & chain of custody | ~92 | — | Per-frame UTC in MP4 export (Phase 4). |
| Detection & base | ~58→68 | **Scene** lower-half mean; **LPR** upscale &lt;80 px; **motion** MOG2 + MOTION_THRESHOLD + MOTION_MOG2_VAR_THRESHOLD; **centroid smoothing** (CENTROID_SMOOTHING_FRAMES). | YOLO conf already on crowd_count. |
| Extended visual | ~52→62 | HEIGHT_REF, emotion min crop, pose label, line-cross debounce; **224×224** for DeepFace age/gender (PLAN_90_PLUS). | CLAHE for low light. |
| Audio | ~54 | Stress + energy fusion (Phase 2.5). | Best ASR; keyword expansion. |
| Other/identity | ~52 | — | ReID/watchlist; homography for world_x/y. |

**Applied:** Scene lower-half mean; LPR upscale 80×24; motion MOG2 + MOTION_THRESHOLD + MOTION_MOG2_VAR_THRESHOLD; centroid smoothing (CENTROID_SMOOTHING_FRAMES, default 5) for line-cross; 224×224 resize for DeepFace age/gender. See §10 and **PLAN_90_PLUS_DATA_POINTS.md** for 90+ roadmap.

---

## 1. Provenance & chain of custody (evidence-grade)

| Data point | Current score | Best-in-class reference | Gap | Suggested improvements |
|------------|----------------|--------------------------|-----|-------------------------|
| **timestamp_utc** | 92 | NISTIR 8161 Rev.1: UTC per frame; MISB time codes | No per-frame UTC in export file | Add per-frame or per-segment UTC in MP4 export (timed metadata); NTP in health (done). **Source:** NISTIR 8161, NIST Digital Video Exchange, ONVIF. |
| **date, time** | 88 | NISTIR 8161; system clock + export UTC | Drift if NTP not used | Document NTP requirement in runbooks; use `/health/ready` time_sync_status. **Source:** NISTIR 8161. |
| **model_version** | 95 | NIST AI 100-4: AI provenance | — | Already stored per row. Optional: log confidence or model variant. **Source:** NIST AI 100-4. |
| **system_id** | 95 | NISTIR 8161: equipment ID | — | Set via env; in export headers. **Source:** NISTIR 8161. |
| **integrity_hash** | 95 | SWGDE 23-V-001; OSAC 2024-N-0011 fixity | — | Per-row SHA-256; verify endpoint. Optional: dual-hash for high assurance. **Source:** SWGDE, OSAC. |
| **camera_id** | 90 | LE/correlation | — | Stable per source; optional label in config. |

---

## 2. Detection & base analytics

| Data point | Current score | Best-in-class reference | Gap | Suggested improvements |
|------------|----------------|--------------------------|-----|-------------------------|
| **object** | 62 | COCO mAP; confidence filtering (Ultralytics) | No conf filter historically; YOLO_CONF now used | Use only boxes above YOLO_CONF for primary object; prefer yolov8s/m for higher mAP. **Source:** COCO benchmarking (Springer/arXiv); Ultralytics docs. |
| **crowd_count** | 58 | Count with confidence threshold; NMS | All boxes counted; no conf filter | Apply YOLO_CONF to boxes before counting; optional per-class conf (YOLO_CLASS_CONF). **Source:** Object detection benchmarks; surveillance counting (IEEE). |
| **pose** | 78 | MediaPipe on person crop; Standing/Sitting/Walking from landmarks | Implemented (Phase 2.2); angle-dependent accuracy | Keep person-crop-first; validate on your camera angles; document viewing-angle limits. **Source:** MediaPipe pose accuracy vs motion capture (De Gruyter, PMC); BEST_PATH_FORWARD Phase 2.2. |
| **emotion** | 55→68 | FER benchmarks (FER2013, CK+, KDEF); CLAHE/gamma; 48×48 min | **Applied:** Min crop 48; **CLAHE on L** when mean &lt; EMOTION_CLAHE_THRESHOLD (80); 224×224 age/gender. | Report demographic differentials (what_we_collect face_attributes_note). **Source:** Springer AVES; NIST FRVT demographics. |
| **scene** | 58→72 | Indoor/outdoor 80–90% with features or classifier (Sciencedirect, IEEE) | **Applied:** Lower-half mean; **variance** (Indoor only when mean &lt; 100 and var &lt; SCENE_VAR_MAX_INDOOR). | Optional: lightweight classifier for 80%+. **Source:** Indoor/outdoor (Sciencedirect, IEEE). **Apply:** app.py scene block. |
| **license_plate** | 58 | LPRNet ~90% real plates; preprocessing critical (MDPI, arXiv) | **Applied:** Preprocess on; upscale when ROI &lt; 80×24 px. | Consider LPRNet for 90%+. **Source:** LPR preprocessing (arXiv, IEEE). **Apply:** app.py _lpr_preprocess upscale threshold 80/24; ENABLE_LPR_PREPROCESS=1. |
| **motion** | 62 | MOG2/KNN + morphology; ~90% in studies (IEEE) | **Applied:** MOTION_BACKEND=mog2; MORPH_OPEN; MOTION_THRESHOLD env. | Tune varThreshold per scene. **Source:** IEEE background subtraction. **Apply:** app.py detect_motion; .env MOTION_BACKEND, MOTION_THRESHOLD. |
| **loiter / line_cross / event** | 75→82 | Trajectory smoothing; debounce; PETS-style tuning (Springer 75% recall, 87% prec) | **Applied:** Centroid smoothing (CENTROID_SMOOTHING_FRAMES); debounce; threat_score +10 for line_cross. | Calibrate loiter_seconds per FOV. **Source:** IEEE trajectory; Springer PETS2007; BEST_PATH_FORWARD Phase 2.3. |

---

## 3. Extended visual attributes

| Data point | Current score | Best-in-class reference | Gap | Suggested improvements |
|------------|----------------|--------------------------|-----|-------------------------|
| **estimated_height_cm** | 55 | Single-view metrology with calibration (Criminisi; Sciencedirect); reference object | Heuristic 170×ratio; clamp 120–220; calibration optional | Use HEIGHT_REF_CM/HEIGHT_REF_PX per camera (done); document calibration; optional vanishing-point method for metric height. **Source:** Single view metrology (Springer); surveillance height (Sapienza, Sciencedirect). |
| **build** | 40 | Bbox aspect heuristic only | No learned model | Document as heuristic; optional body-shape model if needed for use case. **Source:** Heuristic; no universal LE standard. |
| **hair_color** | 50 | Dominant color in ROI | Illumination and ROI sensitive | Use consistent ROI (top 25%); optional illuminant normalization. **Source:** Color naming (vision); no formal LE benchmark. |
| **clothing_description** | 50 | Dominant color lower body | Same as hair | Document as coarse descriptor; sufficient for re-id cues. **Source:** ReID literature. |
| **perceived_gender** | 50 | NIST FRVT demographics; 224×224; demographic reporting | DeepFace not FRVT-validated; demographic differentials | Resize crop to 224×224 for DeepFace; document “not FRVT-validated”; optional demographic audit (NISTIR 8429). **Source:** NIST FRVT, NISTIR 8280/8429; Gender Shades. |
| **perceived_age_range** | 48 | Same as gender; resolution and alignment | Same as gender | 224×224 input; face alignment if available; document bands and uncertainty. **Source:** NIST FRVT; DeepFace/InsightFace resolution (arXiv). |
| **perceived_ethnicity** | 35 | Policy-sensitive; NIST demographic reporting | DeepFace race; opt-in only | If used: report demographic differentials; prefer not for LE without policy. **Source:** NISTIR 8429; policy (CIVILIAN_ETHICS). |
| **gait_notes** | 65 | MediaPipe-based; normal/bent_torso/asymmetric | Single-frame only | Keep; optional temporal gait model for richer labels. **Source:** GAIT_AND_POSE_OPEN_SOURCE.md. |
| **suspicious_behavior / predicted_intent / anomaly_score / threat_score** | 60 | Event-aligned; learned anomaly (SPAN) in research | Heuristics only | Keep event alignment; optional learned anomaly model; document calibration. **Source:** ACCURACY_RESEARCH; temporal anomaly (academic). |
| **stress_level** | 58 | Emotion-derived; multimodal in research | From emotion only | Keep; optional fuse with audio stress when both present. **Source:** Stress from FER (academic). |
| **micro_expression / attention_region** | 25 | MER models; gaze models | Stubs | Implement MER/gaze only if use case requires; document as stub. **Source:** Micro-expression (academic). |
| **intoxication_indicator / drug_use_indicator** | 20 | No reliable single-frame vision standard | Stubs | Leave as stub or remove from export if not used; document. **Source:** Policy-sensitive; no LE standard. |
| **centroid_nx, centroid_ny / world_x, world_y** | 82 | Homography for floor plane (MAPPING_OPTIMIZATION_RESEARCH) | world_x/y need homography config | Add homography per camera for mapping; centroid already normalized. **Source:** NISTIR 8161 metadata; ONVIF; MAPPING_OPTIMIZATION_RESEARCH. |
| **illumination_band / period_of_day_utc** | 70 | Simple bands | — | Keep; optional finer bands or classifier. **Source:** Evidence context (NISTIR). |

---

## 4. Audio attributes

| Data point | Current score | Best-in-class reference | Gap | Suggested improvements |
|------------|----------------|--------------------------|-----|-------------------------|
| **audio_transcription** | 50 | WER <10% target (Deepgram, arXiv); Whisper/Google | Depends on backend; WER not measured | Use best ASR available; document backend and WER if known; target <15% WER for emotion. **Source:** SER + ASR (arXiv); BERSt benchmark. |
| **audio_sentiment / audio_emotion** | 52 | Keyword + acoustic fusion; SER benchmarks (IEMOCAP, MSP-Podcast) | Keyword-based; emotion fusion done | Keep keyword sets; fuse energy (done); optional SER model for acoustic emotion. **Source:** Interspeech 2025 SER challenge; multimodal SER (arXiv). |
| **audio_stress_level** | 62 | Keyword + energy fusion | Fusion implemented (Phase 2.5) | Expand threat/stress keyword sets from real incidents; optional prosody features. **Source:** Phase 2.5; SER benchmarks. |
| **audio_energy_db / audio_background_type** | 75 | RMS/dB standard | — | Keep; used for anomaly and stress fusion. **Source:** Audio analysis (academic). |
| **audio_threat_score / audio_anomaly_score** | 58 | Keyword + energy | — | Keep formula; align with incident review; document. **Source:** ACCURACY_RESEARCH. |
| **audio_speech_rate** | 70 | words / duration | — | Keep when duration available. **Source:** Speech analytics. |
| **audio_speaker_gender / audio_speaker_age_range / audio_intoxication_indicator** | 25 | Voice biometrics (stubs) | Stubs | Implement only if use case requires; document. **Source:** Voice demography (academic). |

---

## 5. Other sensors & identity

| Data point | Current score | Best-in-class reference | Gap | Suggested improvements |
|------------|----------------|--------------------------|-----|-------------------------|
| **individual / face_match_confidence** | 45 | ReID/watchlist; NIST FRVT for face | “Unidentified” default; watchlist optional | Enable watchlist/ReID when needed; document FRVT/demographic limits. **Source:** NIST FRVT; IDENTITY_MARKERS_AND_REID.md. |
| **zone_presence** | 70 | Zone logic from config | — | Keep; document zone definitions. **Source:** Analytics (MAPPING_OPTIMIZATION_RESEARCH). |
| **device_mac / device_oui_vendor / device_probe_ssids** | 65 | WiFi presence; OUI lookup | Completeness depends on capture | Document antenna/channel best practices; no ML standard. **Source:** RESEARCH_MILITARY_CIVILIAN_ACADEMIC_LE. |
| **thermal_signature** | 30 | FLIR/Lepton if hardware | Stub without hardware | Use only with thermal hardware; document. **Source:** Optional sensor. |

---

## 6. Summary: scores by category

| Category | Avg score (approx) | Top gaps |
|----------|--------------------|----------|
| Provenance & chain of custody | 92 | Per-frame UTC in export |
| Detection & base | 58 | Object/crowd conf; scene; LPR preprocessing; motion backend |
| Extended visual | 52 | Age/gender 224×224 + demographic reporting; height calibration; stubs |
| Audio | 54 | ASR quality; SER/acoustic emotion |
| Other/identity | 52 | ReID/watchlist; demographic reporting for face |

---

## 7. Prioritized improvements to reach best-in-class (by data point)

1. **object / crowd_count:** Apply YOLO_CONF consistently; consider yolov8s/m. **Sources:** COCO/Ultralytics; surveillance benchmarks.
2. **scene:** Replace single mean with lower-half mean + variance or simple classifier (target 80%+). **Sources:** IEEE, Sciencedirect indoor/outdoor.
3. **license_plate:** Enforce LPR preprocessing; upscale small ROI; consider LPRNet (target ~90%). **Sources:** MDPI, arXiv, IEEE PGFLP.
4. **motion:** Add optional MOG2 backend + morphology + contour filter (target ~90% in controlled studies). **Sources:** IEEE background subtraction.
5. **emotion:** Add CLAHE/gamma for low light; 224×224 for age/gender; document demographic limits. **Sources:** Springer AVES; low-light FER; NIST FRVT.
6. **perceived_gender / perceived_age_range:** 224×224 input; NIST FRVT or internal demographic audit; document “not FRVT-validated.” **Sources:** NISTIR 8280/8429; Gender Shades.
7. **estimated_height_cm:** Use HEIGHT_REF_CM/HEIGHT_REF_PX per camera; document calibration. **Sources:** Single-view metrology; surveillance height (Sapienza, Sciencedirect).
8. **audio_transcription / audio_emotion:** Best ASR (Whisper/Deepgram/Google); fuse acoustic (done); target WER <15% for SER. **Sources:** Interspeech SER; arXiv SER+ASR.
9. **timestamp_utc (export):** Per-frame or per-segment UTC in MP4. **Sources:** NISTIR 8161; ONVIF; MISB.
10. **loiter/line_cross:** Centroid smoothing (moving avg); keep debounce. **Sources:** IEEE trajectory; Springer PETS2007.

---

## 8. References (military, law enforcement, academic)

- **NISTIR 8161 Rev.1** — CCTV digital video export; UTC, metadata, chain of custody (NIST/FBI).
- **NIST FRVT / NISTIR 8280, 8429** — Face recognition accuracy; demographic differentials (NIST).
- **SWGDE 23-V-001** — Digital video authentication (SWGDE).
- **OSAC 2024-N-0011** — Forensic digital image management; fixity (OSAC/NIST).
- **COCO / Ultralytics** — Object detection mAP; confidence thresholding (Springer, arXiv).
- **LPR:** Preprocessing and LPRNet (MDPI, arXiv, IEEE PGFLP); PatrolVision.
- **FER / low-light:** AVES preprocessing (Springer); LLDif; joint learning low-light FER.
- **MediaPipe Pose** — Accuracy vs motion capture (De Gruyter, PMC); viewing angle dependency.
- **Indoor/outdoor** — Scene classification 80–90% (Sciencedirect, IEEE).
- **Background subtraction** — MOG2 evaluation (IEEE, Semanticscholar).
- **Height estimation** — Single-view metrology (Springer Criminisi); surveillance calibration (Sapienza, Sciencedirect).
- **SER/ASR** — Interspeech 2025 SER; WER impact on SER (arXiv); BERSt benchmark.
- **Trajectory/loitering** — IEEE; Springer PETS2007.
- **Gender Shades** — Demographic accuracy in face analysis (Buolamwini et al.).

---

## 9. Cross-references

- **ACCURACY_RESEARCH_AND_IMPROVEMENTS.md** — Per-field sources and improvements (implemented and planned).
- **DATA_COLLECTION_RESEARCH.md** — Pipeline, config, log export score.
- **BEST_PATH_FORWARD_HIGHEST_STANDARDS.md** — Phased roadmap; many items above are Phase 2/4.
- **RESEARCH_MILITARY_CIVILIAN_ACADEMIC_LE.md** — Military, civilian, academic, LE sources.
- **STANDARDS_APPLIED.md** — What is integrated; next steps.

---

## 10. Applied improvements (from this rating)

| Data point | Change | Where |
|------------|--------|--------|
| **scene** | Use **lower-half mean** instead of full-frame mean for Indoor/Outdoor (reduces sky bias; target ~80% with simple features). | app.py: scene = mean(frame[h//2:, :]) &lt; 100. |
| **license_plate** | **Upscale** ROI when width &lt; 80 px or height &lt; 24 px (was 40/12); min output 160×48 after 2×. | app.py: _lpr_preprocess. |
| **motion** | **MOTION_BACKEND=mog2**: MOG2 background subtractor with detectShadows; MORPH_OPEN on foreground; **MOTION_THRESHOLD** env (100–10000, default 500). | app.py: detect_motion; .env.example MOTION_BACKEND, MOTION_THRESHOLD. |
