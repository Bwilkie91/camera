# Data Collection — Research and Improvements

This document summarizes how Vigil collects AI detection data, improvements made for consistency and accuracy, and research-backed next steps. See also **AUDIT_DATA_COLLECTION.md** (chain of custody) and **ACCURACY_RESEARCH_AND_IMPROVEMENTS.md** (per-field accuracy).

---

## 1. Collection pipeline (summary)

- **Gate**: Data is collected only while **recording is on** (`is_recording` in `analyze_frame()`). When recording stops, the pipeline flushes any buffered `ai_data` and then only sleeps; no new YOLO/pose/emotion/motion/audio runs.
- **Flow**: Each cycle (interval `ANALYZE_INTERVAL_SECONDS`): read frame → YOLO (with `YOLO_CONF` and `_filter_yolo_results`) → pose (MediaPipe) → emotion → scene, LPR, motion, loiter/line-cross → build `data` dict → merge extended attributes and audio → normalize row → append to `_ai_data_batch` → batch INSERT when size ≥ `AI_DATA_BATCH_SIZE`, or flush on recording stop.
- **Schema**: `ai_data` has a fixed canonical column set (`AI_DATA_EXPORT_COLUMNS`). Exports use this order; integrity hash uses `_AI_DATA_HASH_ORDER`.

---

## 2. Improvements implemented

### 2.1 Consistent row shape

- **Before**: Each row could have different keys (e.g. no centroid when no person), so INSERT column list varied and CSV/analytics had to handle variable columns.
- **After**: Before append, the row is normalized to **all** keys in `AI_DATA_EXPORT_COLUMNS`; missing values are `None`. Batch insert uses the same column list for every row (`tuple(row.get(k) for k in cols)`). Export and downstream analytics see a stable schema.

### 2.2 Primary person consistency

- **Before**: Centroid came from the **largest** person bbox; extended attributes (height, build, hair, clothing) came from the **first** person in the loop, so they could refer to different people.
- **After**: Extended attributes use the **same primary person** as the centroid: largest person bbox by area. So `centroid_nx/ny`, `estimated_height_cm`, `hair_color`, `clothing_description`, and `build` all refer to the same subject when multiple people are present.

### 2.3 Estimated height scaling

- **Before**: Reference height in pixels was `min(frame_h, 450)`, so at low resolution or odd aspect ratios height could be biased (e.g. 220 cm cap hit too often).
- **After**: Reference is `max(100, frame_h * 0.45)` so the same physical person at different resolutions gives a more consistent estimate; clamp remains 120–220 cm.

---

## 3. Data quality notes (from sample logs)

- **perceived_gender / hair_color**: In exports, “gray” in the gender column is usually **hair_color** (dominant color in top 25% of person ROI). Demographics (gender/age) come from DeepFace/EmotiEffLib only when `ENABLE_EXTENDED_ATTRIBUTES=1` and a face is detected; otherwise those fields are null.
- **estimated_height_cm**: 220 is the upper clamp; it can be reached when the primary person bbox is large (e.g. person close to camera). The new ref scaling reduces spurious 220s for distant persons on tall frames.
- **Centroid / world_x,y**: Set only when at least one person is detected; otherwise null. Homography (`config/homography.json`) maps normalized centroid to floor-plane `world_x`, `world_y` when configured.

---

## 4. Research-backed next steps (from ACCURACY_RESEARCH_AND_IMPROVEMENTS.md)

| Area | Suggestion | Effort |
|------|------------|--------|
| **YOLO** | Already using `YOLO_CONF` and per-class `YOLO_CLASS_CONF`; consider larger model (e.g. yolov8s/m) for better recall. | Low |
| **Emotion** | Preprocess crop (CLAHE/gamma) when mean intensity low; minimum crop size 48×48 for DeepFace. | Medium |
| **Pose** | Already running MediaPipe on person crop fallback; optional: richer label (Sitting/Walking/Standing) from landmarks. | Medium |
| **Scene** | Use mean of lower half or mean+variance; optional lightweight indoor/outdoor classifier. | Low–Medium |
| **LPR** | Preprocess ROI (grayscale, CLAHE, morph); upscale small ROIs before Tesseract. | Medium |
| **Motion** | Optional MOG2/KNN background subtractor; morphology and contour area filter. | Medium |
| **Loiter/line** | Centroid smoothing over last K frames; debounce line cross (require 1–2 cycles on opposite side). | Medium |

---

## 5. Configuration affecting collection

| Env / config | Effect |
|--------------|--------|
| `ANALYZE_INTERVAL_SECONDS` | Seconds between analysis cycles (default 10). |
| `AI_DATA_BATCH_SIZE` | Rows buffered before commit (default 10; max 50). |
| `YOLO_CONF`, `YOLO_CLASS_CONF` | Confidence thresholds; lower = more detections, more false positives. |
| `ENABLE_EXTENDED_ATTRIBUTES` | When 1, collect perceived_gender, perceived_age_range, build, hair, height, clothing, gait_notes, etc. |
| `ENABLE_SENSITIVE_ATTRIBUTES` | When 1, collect perceived_ethnicity (DeepFace race). |
| `ENABLE_GAIT_NOTES` | When 1, derive gait_notes from MediaPipe pose. |
| Recording config `ai_detail` | `full` = extended attributes; `minimal` = date, time, event, object, camera_id, timestamp_utc only. |
| Recording config `capture_audio` | When true, fill audio_* fields from microphone/transcription. |

---

## 6. References

- **AUDIT_DATA_COLLECTION.md** — Data collection and chain-of-custody audit.
- **AI_DETECTION_LOGS_STANDARDS.md** — NISTIR 8161, SWGDE, export integrity.
- **ACCURACY_RESEARCH_AND_IMPROVEMENTS.md** — Per-field sources and accuracy improvements.
- **GAIT_AND_POSE_OPEN_SOURCE.md** — Pose and gait notes (MediaPipe).
