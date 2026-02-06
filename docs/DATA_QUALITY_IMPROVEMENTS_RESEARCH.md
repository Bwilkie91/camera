# Data Quality Improvements — Research for Highest Standard (1–100)

This document summarizes **extensive research** on additional elements and practices to raise Vigil’s overall data quality score from **72** toward **85–95** (highest standard). It complements **DATA_QUALITY_RATING_SAMPLE.md**, **DATA_POINT_ACCURACY_RATING.md**, and **PLAN_90_PLUS_DATA_POINTS.md**.

---

## 1. Implemented in this pass (score impact)

| Improvement | Effect | Reference |
|-------------|--------|-----------|
| **detection_confidence** (YOLO conf for primary person) | Provenance: per-row model confidence (NIST AI 100-4 style); export and verify include it. | NIST AI 100-4; SWGDE/OSAC metadata. |
| **HEIGHT_MIN_PX** (default 60) | Only compute estimated_height_cm when person bbox height ≥ this; reduces 120 cm outliers from tiny bboxes. | Single-view metrology (IEEE 6233137; Springer); calibration best practice. |
| **Homography calibration docs** | config/README: how to calibrate homography for real world_x, world_y (floor plane). | NISTIR 8161; MAPPING_OPTIMIZATION_RESEARCH; 4-D scene alignment (arXiv 1906.01675). |

---

## 2. Chain of custody (95 → 98+)

| Element | Current | Research / standard | Action |
|--------|---------|---------------------|--------|
| Per-row integrity_hash | ✅ SHA-256 | SWGDE 23-V-001; OSAC 2024-N-0011 | Optional: dual-hash (SHA-256 + SHA3-256) for high assurance. |
| File SHA-256 + X-Export-SHA256 | ✅ | NISTIR 8161; OSAC | Maintain. |
| Verify API | ✅ GET /api/v1/ai_data/verify | Same | Maintain. |
| Per-frame UTC in MP4 | ❌ | NISTIR 8161 Rev.1; ONVIF; MISB | Add per-frame or per-segment UTC in MP4 export (timed metadata). |
| Detection/model confidence | ✅ detection_confidence | NIST AI 100-4 provenance | Implemented; keep in export and hash. |

**Sources:** NISTIR 8161 Rev.1 (CCTV export); SWGDE 23-V-001; OSAC 2024-N-0011; NIST AI 100-4 (synthetic content / provenance).

---

## 3. Identity & demographics (42 → 75+)

| Element | Current | Research | Action |
|--------|---------|----------|--------|
| Face in frame | Often empty in samples | NIST FRVT; ISO 30137-1 | Ensure camera angle and distance allow face crop ≥ 48 px (ideally 224×224 for DeepFace). |
| Watchlist / ReID | ENABLE_WATCHLIST, ENABLE_REID | NIST FIVE 2024; CHIRLA/MTMMC (Nature, CVPR) | Enable when needed; document demographic limits (NISTIR 8429). |
| individual / face_match_confidence | Unidentified when no match | Same | Populate when watchlist/ReID used. |
| perceived_* (age, gender, ethnicity) | Raw DeepFace; 224×224 | NIST FRVT demographics; ISO 30137-1 | Already raw; document “not FRVT-validated” and optional audit. |

**Sources:** NIST FRVT/FIVE; NISTIR 8280, 8429; ISO/IEC 30137-1:2024; Gender Shades; IDENTITY_MARKERS_AND_REID.md.

---

## 4. Physical & context (68 → 82+)

| Element | Current | Research | Action |
|--------|---------|----------|--------|
| estimated_height_cm | HEIGHT_REF_CM/PX; clamp 120–220; **HEIGHT_MIN_PX** | Single-view metrology (Criminisi; IEEE 6233137); Sapienza/Sciencedirect | Use HEIGHT_MIN_PX=60; calibrate HEIGHT_REF per camera; optional vanishing-point method. |
| world_x, world_y | Homography from config | NISTIR 8161; 4-D scene alignment (arXiv 1906.01675); floor-plane homography | Calibrate config/homography.json with 4+ point correspondences (floor → plan). |
| build | Bbox aspect heuristic | No universal LE standard | Document as heuristic; optional body-shape model. |
| hair_color / clothing_description | Dominant color ROI | ReID literature | Illuminant normalization optional. |
| scene (Indoor/Outdoor) | Lower-half mean + variance | IEEE 7050698, 5418764; Sciencedirect; ~86% with sky/vegetation | Optional: lightweight classifier (80–90%); or add sky/vegetation detection. |

**Sources:** IEEE 6233137 (height calibration); Springer single-view metrology; MAPPING_OPTIMIZATION_RESEARCH.md; indoor/outdoor (IEEE, Sciencedirect).

---

## 5. Behavioral alignment (85 → 90+)

| Element | Current | Research | Action |
|--------|---------|----------|--------|
| event / threat / anomaly / intent | Heuristics aligned | PETS2007 (Springer); IEEE trajectory | Centroid smoothing + debounce done; calibrate loiter_seconds per FOV. |
| Learned anomaly | ❌ | SPAN-style temporal anomaly (academic) | Optional: learned anomaly model for threat/anomaly. |

**Sources:** Springer PETS2007; IEEE trajectory; ACCURACY_RESEARCH_AND_IMPROVEMENTS.md.

---

## 6. Audio (25 → 55+)

| Element | Current | Research | Action |
|--------|---------|----------|--------|
| ASR (transcription) | Backend-dependent | WER <15% target for SER (arXiv 2406.08353); Whisper/Deepgram/Google | Use best ASR available; document WER if known. |
| SER (emotion/stress) | Keyword + energy fusion | IEMOCAP; fusion with ASR (arXiv 2406.08353); Odyssey 2024 | Expand keyword sets; optional SER model (IEMOCAP/MSP-Podcast); fusion with acoustic. |
| audio_speaker_gender/age | Stubs | Voice demography (academic) | Implement only if use case requires. |

**Sources:** arXiv 2406.08353 (SER with ASR, WER, fusion); IEMOCAP; IEEE SER; Interspeech.

---

## 7. Scene classification (72 → 85+)

| Approach | Accuracy (literature) | Effort |
|----------|------------------------|--------|
| Lower-half mean + variance (current) | ~72% (PLAN_90_PLUS) | Done |
| Sky + vegetation detection | ~86% (MIT/outdoor-indoor) | Medium |
| Lightweight CNN / two-stage | 80–90% (IEEE 5418764, 7796998) | High |

**Sources:** IEEE 7050698, 5418764, 1047420, 7796998; people.csail.mit.edu indoor-outdoor.

---

## 8. Object detection & crowd (62 → 88+)

| Element | Current | Research | Action |
|--------|---------|----------|--------|
| YOLO_CONF / per-class conf | Applied in _filter_yolo_results | COCO/Ultralytics; surveillance benchmarks | Use filtered results for primary object and crowd_count (done). |
| YOLO model size | yolov8n default | YOLO26n 40.9 mAP50-95; YOLO26x 57.5 (Ultralytics) | Prefer yolov8s/m for higher mAP when CPU/GPU allows. |

**Sources:** Ultralytics validation; COCO mAP; PLAN_90_PLUS_DATA_POINTS.md.

---

## 9. LPR (58 → 78+)

| Element | Current | Research | Action |
|--------|---------|----------|--------|
| Preprocess + upscale <80×24 px | Done | PGFLP IEEE; LPRNet ~90%; AAMVA | Consider LPRNet or dedicated LPR model for 90%+. |

**Sources:** MDPI/arXiv LPR; IEEE PGFLP; PLAN_90_PLUS_DATA_POINTS.md.

---

## 10. Motion (62 → 82+)

| Element | Current | Research | Action |
|--------|---------|----------|--------|
| MOG2 + MORPH_OPEN + MOTION_THRESHOLD | Done | IEEE background subtraction; ~90% in studies | Tune MOTION_MOG2_VAR_THRESHOLD per scene; optional contour area filter. |

**Sources:** IEEE/Semanticscholar; DATA_POINT_ACCURACY_RATING.md.

---

## 11. Summary: actions by impact on overall score

| Priority | Action | Dimension | Est. gain |
|----------|--------|------------|-----------|
| P0 | **Homography calibration** (config/homography.json with real H) | Physical & context | +5–8 |
| P0 | **HEIGHT_MIN_PX=60** + HEIGHT_REF per camera | Physical & context | +3–5 |
| P0 | **detection_confidence** in export (done) | Chain of custody / schema | +1–2 |
| P1 | Face in frame + ENABLE_WATCHLIST/ReID when needed | Identity | +8–12 |
| P1 | Best ASR + SER fusion / keywords | Audio | +5–10 |
| P2 | Per-frame UTC in MP4 export | Chain of custody | +1–2 |
| P2 | Optional scene classifier or sky/veg | Physical & context | +2–4 |
| P2 | YOLO s/m for higher mAP | Schema/detection | +1–2 |

**Target:** With P0 + P1 (homography, height, identity when face present, audio), overall **72 → 85+** is realistic. With P2 and optional learned anomaly / LPRNet, **88–92** is in range.

---

## 12. References (consolidated)

- **NIST:** NISTIR 8161 Rev.1 (CCTV export); FRVT/FIVE/FATE; NISTIR 8280, 8429; AI 100-4 (provenance).
- **ISO:** ISO/IEC 30137-1:2024 (VSS biometrics; age, gender, gait).
- **SWGDE / OSAC:** 23-V-001 (video auth); 2024-N-0011 (fixity).
- **Object / scene:** Ultralytics/COCO; IEEE 7050698, 5418764 (indoor/outdoor); Springer PETS2007.
- **Height:** IEEE 6233137; Springer single-view metrology; Sapienza/Sciencedirect.
- **Homography:** NISTIR 8161; arXiv 1906.01675 (4-D scene alignment); MAPPING_OPTIMIZATION_RESEARCH.md.
- **Audio/SER:** arXiv 2406.08353 (SER+ASR, WER, fusion); IEMOCAP; Interspeech; Odyssey 2024.
- **ReID/identity:** NIST FIVE; CHIRLA (Nature); MTMMC (CVPR); IDENTITY_MARKERS_AND_REID.md.

---

## 13. Cross-references

- **DATA_QUALITY_RATING_SAMPLE.md** — Overall 72/100 breakdown and how to reach 85+.
- **DATA_POINT_ACCURACY_RATING.md** — Per–data-point scores and improvements.
- **PLAN_90_PLUS_DATA_POINTS.md** — Phased 90+ plan (Phase A/B/C/D).
- **BEST_PATH_FORWARD_HIGHEST_STANDARDS.md** — Phased roadmap.
- **config/README.md** — Homography calibration for world_x, world_y.
