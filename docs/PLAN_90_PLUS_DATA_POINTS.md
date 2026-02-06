# Plan: Bring Each Data Point to 90+ (Enterprise-Grade)

This document is the **master plan** to raise every Vigil data point to **90+** (1–100 scale) using **enterprise, military, law enforcement, and academic** research. It references standards (NIST, ISO, SWGDE, ONVIF), benchmarks (NIST FRVT/FIVE, COCO, IEMOCAP, PGFLP), and peer-reviewed work. Implementation is phased; **Phase A** items are started first.

**Sources:** NISTIR 8161, NIST FRVT/FIVE/FATE, ISO/IEC 30137-1:2024, SWGDE 23-V-001, OSAC 2024-N-0011, ONVIF Export, Ultralytics/COCO, IEEE (MOG2, scene, LPR), Springer (FER, loitering), MDPI/arXiv (LPR), ACM/Interspeech (SER), Nature/CVPR (ReID).

---

## Phase A — Quick wins (already partially applied or low effort)

| Data point | Current→Target | Action | Source / standard |
|------------|-----------------|--------|--------------------|
| **object** | 62→88 | YOLO_CONF and _filter_yolo_results already applied; use filtered results for primary object and count. Prefer yolov8s/m for higher mAP (YOLO26n 40.9 mAP50-95; YOLO26x 57.5). | Ultralytics validation; COCO mAP (Springer/arXiv). |
| **crowd_count** | 58→88 | Same: count only boxes that pass _filter_yolo_results (already done). Document; optional per-class conf. | Object detection benchmarks. |
| **scene** | 58→75 | Lower-half mean applied. Add variance: Indoor if mean_lower < 100 and var < threshold; or optional lightweight classifier (target 80–90%). | IEEE 7050698; Sciencedirect; deep learning scene (IEEE 5418764). |
| **license_plate** | 58→78 | Preprocess + upscale 80 px applied. Add optional LPRNet or dedicated LPR model (90%+); document AAMVA best practices. | PGFLP IEEE; LPRNet 90%; AAMVA best practices. |
| **motion** | 62→82 | MOG2 + MORPH_OPEN applied. Tune varThreshold (env); optional contour area filter. | IEEE/Semanticscholar; 90% precision in studies. |
| **timestamp_utc** | 92→98 | Add per-frame or per-segment UTC in MP4 export (timed metadata). NTP done. | NISTIR 8161 Rev.1; ONVIF Export; NIST Digital Video Exchange. |
| **perceived_gender / perceived_age_range** | 48–50→85 | Resize person crop to **224×224** before DeepFace.analyze(age, gender); document “not FRVT-validated”; optional demographic audit. | NIST FRVT/FATE; NISTIR 8525 (age); ISO 30137-1:2024 (age/gender in VSS). |
| **centroid / world_x,y** | 82→92 | Homography per camera for world_x/y; centroid already normalized. Calibrate config/homography.json (see config/README). | NISTIR 8161; MAPPING_OPTIMIZATION_RESEARCH. |
| **detection_confidence** | —→95 | **Applied:** YOLO confidence for primary person per row; export and verify. | NIST AI 100-4. |
| **estimated_height_cm** (outliers) | 55→72 | **Applied:** HEIGHT_MIN_PX=60 so height only when bbox ≥ 60 px; reduces 120 cm outliers. | IEEE 6233137; single-view metrology. |

---

## Phase B — Core accuracy (medium effort)

| Data point | Current→Target | Action | Source / standard |
|------------|----------------|--------|--------------------|
| **emotion** | 55→82 | CLAHE/gamma when mean intensity < threshold (AVES-style); min crop 48 done; 224×224 for age/gender path. Report demographic caveats. | Springer AVES ~11% gain; low-light FER (LLDif); NIST FRVT demographics. |
| **pose** | 78→88 | Person-crop-first done; validate on deployment angles; document limits. Optional: finer Sitting/Walking from landmarks. | MediaPipe vs motion capture (De Gruyter, PMC); ISO 30137 (gait). |
| **estimated_height_cm** | 55→78 | HEIGHT_REF per camera done; HEIGHT_MIN_PX=60 done. Document calibration; optional vanishing-point method. | Single-view metrology (Springer); surveillance height (Sapienza, Sciencedirect). |
| **loiter / line_cross** | 75→88 | Centroid smoothing (moving avg over 3–5 frames) for primary; debounce done. Calibrate loiter_seconds per FOV. | IEEE trajectory; Springer PETS2007 (75% recall, 87% prec). |
| **integrity_hash / model_version / system_id** | 95→98 | Optional dual-hash (SHA-256 + SHA3-256) for high assurance; document. | SWGDE 23-V-001; OSAC fixity. |

---

## Phase C — Extended attributes and audio (higher effort)

| Data point | Current→Target | Action | Source / standard |
|------------|----------------|--------|--------------------|
| **audio_transcription** | 50→82 | Best ASR (Whisper/Deepgram/Google); target WER <15% for SER; document backend. | SER+ASR (arXiv); BERSt; Interspeech. |
| **audio_emotion / audio_stress_level** | 52–62→80 | Acoustic fusion done; optional SER model (IEMOCAP/MSP-Podcast); expand keyword sets. | IEMOCAP; Odyssey 2024 SER; Interspeech 2025. |
| **individual / face_match_confidence** | 45→85 | ReID/watchlist; NIST FRVT or FIVE for face-in-video; document demographic limits. | NIST FIVE 2024; ISO 30137-1; CHIRLA/MTMMC (Nature, CVPR). |
| **suspicious_behavior / threat_score / anomaly_score** | 60→78 | Keep event alignment; optional learned anomaly model (SPAN-style); document calibration. | Temporal anomaly (academic); PETS. |
| **perceived_ethnicity** | 35→70 | If enabled: 224×224; report demographic differentials (NISTIR 8429); policy-only. | NISTIR 8429; CIVILIAN_ETHICS. |

---

## Phase D — Optional / stubs and provenance to 95+

| Data point | Current→Target | Action | Source / standard |
|------------|----------------|--------|--------------------|
| **micro_expression / attention_region** | 25→60 | MER/gaze only if use case requires; else document as stub. | Micro-expression (academic). |
| **intoxication_indicator / drug_use_indicator** | 20→40 | Document as heuristic/stub; no LE standard for single-frame. | Policy. |
| **audio_speaker_gender / audio_speaker_age_range** | 25→50 | Voice demography model only if required; else stub. | Voice (academic). |
| **thermal_signature** | 30→80 | With FLIR/Lepton hardware; document. | Optional sensor. |
| **Export: per-frame UTC, signed manifest** | — | MP4 timed metadata; optional digital signature (SWGDE). | NISTIR 8161; ONVIF; SWGDE 23-V-001. |

---

## Implementation order (begin with Phase A)

1. **224×224 for DeepFace age/gender** — Resize person crop to 224×224 before `DeepFace.analyze(crop, actions=['age','gender'])` when crop smaller; improves NIST/ISO alignment (Phase A).
2. **Centroid smoothing** — Moving average of primary centroid over 3–5 frames; use smoothed centroid for loiter zone and line-cross (Phase B; started in Phase A batch).
3. **Scene variance** — Add variance to scene rule (e.g. Indoor if lower-half mean < 100 and var < 5000) (Phase A).
4. **MOG2 varThreshold env** — Allow tuning `MOTION_MOG2_VAR_THRESHOLD` (Phase A).
5. **Document** — In EXTENDED_ATTRIBUTES or ACCURACY: 224×224 for age/gender; “not FRVT-validated”; demographic audit optional.
6. **Per-frame UTC in MP4** — Phase 4 / separate task (NISTIR 8161).
7. **LPRNet or dedicated LPR** — Optional model integration for 90%+ (Phase B/C).
8. **ReID/watchlist** — Already available; document FIVE/FRVT limits (Phase C).

---

## References (enterprise, military, LE, academic)

- **NIST:** NISTIR 8161 Rev.1 (CCTV export); FRVT, FIVE, FATE (face/age/demographics); NISTIR 8280, 8429 (demographics); Digital Video Exchange.
- **ISO:** ISO/IEC 30137-1:2024 (biometrics in VSS; age, gender, gait); 30137-4 (annotation).
- **SWGDE / OSAC:** 23-V-001 (video authentication); OSAC 2024-N-0011 (fixity).
- **ONVIF:** Export File Format (per-frame time, signature).
- **Object detection:** Ultralytics YOLO validation; COCO mAP; YOLOBench.
- **LPR:** PGFLP (IEEE); LPRNet 90%; AAMVA best practices; preprocessing (MDPI, arXiv).
- **FER / low-light:** AVES (Springer); LLDif; FER2013, CK+, KDEF.
- **Pose:** MediaPipe (De Gruyter, PMC); ISO 30137 gait.
- **Scene:** Indoor/outdoor (IEEE 7050698, 5418764; Sciencedirect).
- **Motion:** MOG2 evaluation (IEEE, Semanticscholar).
- **Height:** Single-view metrology (Springer); surveillance (Sapienza, Sciencedirect).
- **SER/ASR:** IEMOCAP; Odyssey 2024; Interspeech 2025; WER impact (arXiv).
- **ReID:** CHIRLA (Nature); MTMMC (CVPR); IDENTITY_MARKERS_AND_REID.
- **Loitering:** IEEE trajectory; Springer PETS2007.

---

## Cross-references

- **DATA_POINT_ACCURACY_RATING.md** — Per-point scores and improvements.
- **BEST_PATH_FORWARD_HIGHEST_STANDARDS.md** — Phased roadmap.
- **STANDARDS_APPLIED.md** — What is integrated.
- **ACCURACY_RESEARCH_AND_IMPROVEMENTS.md** — Per-field research.
