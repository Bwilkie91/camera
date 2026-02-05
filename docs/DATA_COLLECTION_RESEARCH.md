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

## 3.1 Log export quality score — sample 2/5/26 (1–100, 100 = best in class)

Review of a single exported row (date 2/5/26, time 14:54:48, person, Motion Detected, outdoor, dusk) against best-in-class evidence and analytics standards.

| Dimension | Score | Notes |
|-----------|-------|--------|
| **Chain of custody & provenance** | 92 | `timestamp_utc` (ISO UTC), `model_version` (yolov8n.pt), `system_id` (Mac.attlocal.net), `integrity_hash` present. Missing: export-level SHA-256 and operator in row (handled at export). |
| **Identity & demographics** | 35 | `individual` = "Unidentified"; `perceived_gender` / `perceived_age_range` empty (no face path). Only `hair_color` (gray) and `clothing_description` (gray top/body) populated. Best-in-class: stable ID or face_match_confidence, age/gender when face visible. |
| **Pose, emotion, behavior** | 65 | Pose=Standing, emotion=Neutral, `predicted_intent`=passing, `gait_notes`=normal. `facial_features` duplicates pose/emotion. No Sitting/Walking nuance; emotion from full frame or single crop. |
| **Scene & environment** | 70 | Scene=Outdoor, `illumination_band`=normal, `period_of_day_utc`=dusk. No world_x/world_y (homography not configured). Centroid_nx/ny present (0.40, 0.77). |
| **Threat & anomaly** | 40 | `threat_score`=0, `anomaly_score`=0, `suspicious_behavior`=none. Event="Motion Detected" only; no loiter/line-cross. Best-in-class: calibrated threat/anomaly and behavior labels. |
| **Audio** | 25 | All audio fields None/neutral/silence/0; no transcription or speaker attributes. Acceptable if no mic; otherwise best-in-class needs real ASR + sentiment/emotion. |
| **Accuracy & calibration** | 50 | `estimated_height_cm`=120 (lower clamp — may be real or calibration); `build`=medium. No per-camera height ref or LPR/plate data. |
| **Schema & completeness** | 88 | All canonical columns present; no null column gaps; hash covers canonical set. |

**Overall (weighted toward evidence + identity + behavior):** **~58/100** (baseline sample). Strong on provenance and schema; weak on identity, demographics, threat/behavior nuance, and audio. **Note:** With applied improvements (§4, STANDARDS_APPLIED), pose, emotion, scene, motion, loiter/line, and threat/behavior dimensions are improved; re-scoring the same or a similar sample would yield a higher effective score.

### Improvements to reach best-in-class (90+)

1. **Identity & demographics (→ 85+)**  
   - Enable **ENABLE_EXTENDED_ATTRIBUTES=1** and ensure person/face crop ≥ 48×48 (ideally 224×224 for DeepFace) so `perceived_gender` and `perceived_age_range` populate when a face is detected.  
   - Optionally use ReID/watchlist to replace "Unidentified" with a stable `individual` or set `face_match_confidence` when configured.

2. **Pose & emotion (→ 80+)**  
   - Run MediaPipe on **person crop** (not only full frame) and derive Sitting/Walking/Standing from landmarks.  
   - Preprocess low-light crops (CLAHE/gamma) and use minimum 48×48 crop for emotion so Neutral is not default for poor face visibility.

3. **Threat & behavior (→ 75+)**  
   - Configure loiter zones and crossing lines; use centroid smoothing and debounce so loiter/line-cross events appear when applicable.  
   - Keep threat_score/anomaly_score aligned with events (e.g. loiter → higher anomaly) and document calibration.

4. **Scene & world position (→ 85+)**  
   - Add **homography** (`config/homography.json`) per camera so `world_x`, `world_y` are filled for floor-plane position and mapping/heatmaps.

5. **Audio (if used) (→ 80+)**  
   - Enable `capture_audio` and a quality ASR (e.g. Google/Whisper/Deepgram) so `audio_transcription`, `audio_emotion`, `audio_stress_level` reflect real speech; fuse acoustic features with text for stress.

6. **Height & calibration (→ 70+)**  
   - If many rows sit at 120 or 220 cm, add per-camera `HEIGHT_REF_CM` / `HEIGHT_REF_PX` (or config) and document in ACCURACY_RESEARCH_AND_IMPROVEMENTS.md.

Implementing (1)–(4) and (6) would bring this sample's effective score into the **high 70s–low 80s**; adding (5) when audio is in scope would push toward **90+** for full best-in-class.

**Prioritized roadmap:** See **[BEST_PATH_FORWARD_HIGHEST_STANDARDS.md](BEST_PATH_FORWARD_HIGHEST_STANDARDS.md)** for the full path (config → data quality → security & evidence).

**Applied improvements:** Many of the improvements above are now implemented. See **[STANDARDS_APPLIED.md](STANDARDS_APPLIED.md)**, **[PLAN_90_PLUS_DATA_POINTS.md](PLAN_90_PLUS_DATA_POINTS.md)**, and **[DATA_POINT_ACCURACY_RATING.md](DATA_POINT_ACCURACY_RATING.md)** for what is integrated. Re-score the sample (§3.1) when convenient.

---

## 4. Research-backed next steps (from ACCURACY_RESEARCH_AND_IMPROVEMENTS.md)

| Area | Suggestion | Status |
|------|------------|--------|
| **YOLO** | YOLO_CONF and YOLO_CLASS_CONF; consider larger model (yolov8s/m) for better recall. | **Applied** (filter in place). |
| **Emotion** | CLAHE when mean intensity low; min crop 48×48; 224×224 for age/gender. | **Applied** (EMOTION_CLAHE_THRESHOLD, EMOTION_MIN_CROP_SIZE, 224×224 in app.py). |
| **Pose** | MediaPipe on person crop; Sitting/Walking/Standing from landmarks. | **Applied** (POSE_MIN_CROP_SIZE, _pose_label_from_landmarks). |
| **Scene** | Lower-half mean + variance; optional classifier. | **Applied** (lower-half mean, SCENE_VAR_MAX_INDOOR). |
| **LPR** | Preprocess ROI; upscale small ROIs (&lt;80×24 px). | **Applied** (_lpr_preprocess, ENABLE_LPR_PREPROCESS). |
| **Motion** | MOG2/KNN + morphology; configurable threshold. | **Applied** (MOTION_BACKEND=mog2, MOTION_THRESHOLD, MOTION_MOG2_VAR_THRESHOLD). |
| **Loiter/line** | Centroid smoothing; debounce line cross. | **Applied** (CENTROID_SMOOTHING_FRAMES, LINE_CROSS_DEBOUNCE_CYCLES). |

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
| `EMOTION_MIN_CROP_SIZE` | Min person crop size for emotion (default 48); Phase 2.1. |
| `LINE_CROSS_DEBOUNCE_CYCLES` | Cycles centroid must stay on opposite side before line_cross fires (default 1); Phase 2.3. |
| `POSE_MIN_CROP_SIZE` | Min person crop size for pose (default 48); Phase 2.2. Pose label: Standing / Sitting / Walking from landmarks. |
| `MOTION_BACKEND` | `framediff` (default) or `mog2`; MOG2 + morphology for better motion detection (DATA_POINT_ACCURACY_RATING). |
| `MOTION_THRESHOLD` | Pixel count threshold for motion (100–10000; default 500). |
| `MOTION_MOG2_VAR_THRESHOLD` | MOG2 varThreshold (4–64; default 16) when MOTION_BACKEND=mog2 (PLAN_90_PLUS). |
| `EMOTION_CLAHE_THRESHOLD` | Mean intensity below which CLAHE is applied on L channel for emotion (default 80; 0=off). Phase 2.1. |
| `SCENE_VAR_MAX_INDOOR` | Max lower-half variance for Indoor classification (default 5000); Indoor only when mean &lt; 100 and var &lt; this (PLAN_90_PLUS). |
| `CENTROID_SMOOTHING_FRAMES` | Moving average of primary centroid over N frames for line-cross (default 5; 0=off). PLAN_90_PLUS. |

**Scene:** Indoor/Outdoor uses **lower-half mean** + **variance** (SCENE_VAR_MAX_INDOOR). **LPR:** ROI upscaled when width &lt; 80 px or height &lt; 24 px. **Loiter/line:** Centroid smoothing (CENTROID_SMOOTHING_FRAMES) and line-cross debounce (LINE_CROSS_DEBOUNCE_CYCLES).

**Audio (Phase 2.5):** `audio_stress_level` fuses `energy_db`: very loud audio boosts stress; no transcription but loud → medium. ASR quality (Google/Whisper/Deepgram) remains config.

---

## 6. References

- **AUDIT_DATA_COLLECTION.md** — Data collection and chain-of-custody audit.
- **AI_DETECTION_LOGS_STANDARDS.md** — NISTIR 8161, SWGDE, export integrity.
- **ACCURACY_RESEARCH_AND_IMPROVEMENTS.md** — Per-field sources and accuracy improvements.
- **DATA_POINT_ACCURACY_RATING.md** — Per–data-point rating (1–100) and improvements (military, LE, academic sources).
- **GAIT_AND_POSE_OPEN_SOURCE.md** — Pose and gait notes (MediaPipe).
