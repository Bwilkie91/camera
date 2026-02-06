# Analyzed Data Points & Accuracy Improvement Research

This document catalogs **every analyzed data point** in the Vigil pipeline and summarizes **research-backed ways to improve accuracy** for each. References are from recent CVPR, IEEE, Springer, MDPI, and arXiv work on object detection, FER, LPR, tracking, and audio analysis.

---

## 1. Complete inventory of analyzed data points

### 1.1 Base (per-frame) — from `analyze_frame`

| Data point | Current source | Used for |
|------------|----------------|----------|
| **object** | YOLO: first class name from `results[0].boxes.cls` (no confidence filter) | Primary detected object; event metadata |
| **crowd_count** | `len(results[0].boxes)` (all boxes, no conf filter) | Crowding, aggregates, notable screenshots |
| **pose** | MediaPipe Pose on full frame → `Standing` or `Unknown` | facial_features, extended attributes |
| **emotion** | DeepFace or EmotiEffLib: full frame or person crop; single dominant label | Stress, micro_expression, notable behavior |
| **scene** | `np.mean(frame) < 100` → Indoor else Outdoor | Metadata, search |
| **license_plate** | PyTesseract on vehicle ROI (YOLO bbox for car/truck/bus/motorcycle) | Search, metadata |
| **motion** | Pixel diff (Gaussian blur, threshold 25, count > 500) | Event = Motion Detected |
| **loiter** | Zone ticks: person centroid in polygon for N cycles (config loiter_seconds / 10) | Event = Loitering Detected |
| **line_cross** | Segment crossing: prev vs current centroids vs crossing_lines | Event = Line Crossing Detected |
| **event** | Derived: line_cross > loiter > motion > None | Events table, extended attributes |
| **date, time, timestamp_utc** | System time | All records |
| **camera_id, model_version, system_id** | Config / env | Provenance |
| **integrity_hash** | SHA-256 over canonical ai_data fields | Chain of custody |

### 1.2 Extended attributes (visual) — `_extract_extended_attributes`

| Data point | Current source | Notes |
|------------|----------------|-------|
| **estimated_height_cm** | Person bbox height vs ref 450 px → 170×ratio, clamp 120–220 | Single person bbox |
| **build** | Bbox aspect (width/height): &lt;0.35 slim, &gt;0.5 heavy | Heuristic |
| **hair_color** | Dominant color (BGR mean) in top 25% of person ROI | black/white/red/blue/green/brown/gray |
| **clothing_description** | Dominant color in lower 2/3 body ROI | e.g. "blue top/body" |
| **suspicious_behavior** | From event: loitering / line_crossing / none | |
| **predicted_intent** | From event: loitering / crossing / passing / unknown | |
| **anomaly_score** | 0.0 / 0.5 (loiter) / 0.6 (line_cross) | Event-based |
| **stress_level** | Emotion → high (Angry,Fear,Sad,Disgust), medium (Surprise), low | |
| **threat_score** | Heuristic 0–100: +25 suspicious, +20 high stress, +15 loiter | |
| **micro_expression** | Same as emotion (stub) | MER model would improve |
| **attention_region** | `unknown` (stub) | Gaze model would improve |
| **intoxication_indicator, drug_use_indicator, gait_notes** | Stubs: none / normal | Gait/temporal model needed |
| **perceived_gender** | DeepFace `dominant_gender` on crop (if ENABLE_EXTENDED_ATTRIBUTES) | Raw model output. Not NIST FRVT-validated; see §Demographic fairness below. |
| **perceived_age** | DeepFace `age` (integer) | Raw estimated age in years. |
| **perceived_age_range** | Same `age` as string | Raw age string (e.g. "34"); no bucketing. |
| **perceived_ethnicity** | DeepFace `dominant_race` | Raw model output; stored when extended attributes on. |

### 1.3 Audio attributes — `_extract_audio_attributes`

| Data point | Current source | Notes |
|------------|----------------|-------|
| **audio_transcription** | Speech-to-text (e.g. Google / recognizer) | Same as audio_event |
| **audio_sentiment** | Keyword counts: positive vs negative vs threat | |
| **audio_emotion** | Keyword sets → angry, sad, happy, fear, calm, distress, neutral | |
| **audio_stress_level** | Threat + stress keyword counts → high/medium/low | |
| **audio_threat_score** | threat_k×30 + stress_k×15, cap 100 | |
| **audio_anomaly_score** | Energy (loud/quiet) + threat keywords → 0–0.7 | |
| **audio_energy_db** | RMS → dB | |
| **audio_background_type** | silence / quiet_speech / speech / loud_speech_or_noise | |
| **audio_speech_rate** | words / (duration_sec/60) | |
| **audio_language** | Stub (e.g. en) | |
| **audio_keywords** | Extracted threat/emotion terms | |
| **audio_speaker_gender, audio_speaker_age_range, audio_intoxication_indicator** | Stubs | Voice model needed |

### 1.4 Other sensors

| Data point | Current source | Notes |
|------------|----------------|-------|
| **device_mac, device_oui_vendor, device_probe_ssids** | WiFi worker: scapy probe + OUI lookup | Nearby devices |
| **thermal_signature** | flirpy Lepton or stub | Optional hardware |

---

## 2. Research-backed accuracy improvements (by category)

### 2.1 YOLO (object, crowd_count, person bbox for emotion/height/build)

**Current:** No confidence threshold; all boxes used for `object`, `crowd_count`, and person crop.

**Research:**
- **Confidence threshold**: YOLO outputs many raw candidates; filtering by confidence is essential. Too low → false positives; too high → missed detections. Tuning per use case is standard (Ultralytics docs, Medium).
- **Resolution**: 640 px is typical; validation at different `imgsz` (e.g. 416 vs 640 vs 832) finds optimum for your scene (Ultralytics validation).
- **NMS / IOU**: Ultralytics applies NMS by default; `iou` and `conf` in `predict()` control behavior.

**Improvements:**
1. **Add configurable confidence** (`YOLO_CONF`, default e.g. 0.25): pass `conf=float` to `predict()`; use only boxes above this for `objects` and `crowd_count` and for person crop (emotion, extended attributes).
2. **Filter “object” by confidence**: Use highest-confidence box when multiple; optionally require `conf >= 0.3` for primary object.
3. **Larger model**: `yolov8s.pt` or `yolov8m.pt` for better accuracy at higher compute (document in YOLO_INTEGRATION.md).

---

### 2.2 Emotion (DeepFace / EmotiEffLib)

**Current:** Full frame or first person crop; single dominant label; no preprocessing.

**Research:**
- **Face alignment**: Alignment failures are common in the wild; systems that fuse aligned + non-aligned (e.g. AMN) improve robustness (CVPR workshops).
- **Preprocessing**: CLAHE, gamma correction, Gaussian filtering keyed to image quality (energy, sharpness, contrast) give large gains on noisy/low-res inputs (Springer, AVES: up to ~11% accuracy improvement).
- **Crop quality**: Person bbox crop already used for EmotiEffLib; ensure minimum size (e.g. 48×48 or 64×64) and pad; prefer face detector crop over full person when available.

**Improvements:**
1. **Preprocess crop**: Before DeepFace/EmotiEffLib, run CLAHE or gamma on the face/person crop when mean intensity is low or variance is high (configurable).
2. **Minimum crop size**: Skip emotion or use “Unknown” when person crop &lt; 30×30 (already partially done); consider 48×48 minimum for DeepFace. **Implemented:** `EMOTION_MIN_CROP_SIZE` (default 48) in app.py (BEST_PATH_FORWARD Phase 2.1).
3. **Resolution for DeepFace**: Feed at least 224×224 for age/gender; emotion models also benefit from consistent input size (document in EXTENDED_ATTRIBUTES).

---

### 2.3 Pose (MediaPipe)

**Current:** Full frame; binary Standing / Unknown.

**Research:**
- Pose accuracy improves with consistent resolution and centered person; cropping to person bbox reduces clutter and can improve landmark quality.

**Improvements:**
1. **Person crop for pose**: When YOLO person bbox exists, run MediaPipe on the person crop (with padding) instead of full frame to reduce false landmarks.
2. **Richer pose label**: Use landmark geometry (e.g. spine angle, leg angles) to label Sitting / Walking / Standing instead of binary (optional, for logs).

---

### 2.4 Scene (Indoor / Outdoor)

**Current:** `np.mean(frame) < 100` → Indoor.

**Research:**
- Single global mean is highly sensitive to exposure and content; scene classifiers typically use color histograms, texture, or small CNNs.

**Improvements:**
1. **Simple improvement**: Use mean of lower half of frame (sky vs ground) or mean + variance; e.g. low variance + low mean → Indoor.
2. **Optional classifier**: Lightweight scene model (e.g. indoor/outdoor/road) trained on similar cameras for much better accuracy (future).

---

### 2.5 License plate (LPR)

**Current:** PyTesseract on raw vehicle ROI.

**Research:**
- **Preprocessing is critical**: Grayscale, CLAHE, bilateral filter, adaptive thresholding, morphological open improve OCR accuracy (MDPI, arXiv). YOLO + preprocessing + OCR pipelines are standard.
- **Resolution**: Tesseract needs sufficient resolution; upscale small ROIs (e.g. 2×) before OCR can help.
- **Specialized LPR**: Dedicated LPR models (e.g. LPRNet) reach ~90% on real plates vs lower accuracy with generic Tesseract (arXiv).

**Improvements:**
1. **Preprocess ROI**: Convert to grayscale; apply CLAHE; optional bilateral filter; adaptive threshold; morphological open before `pytesseract.image_to_string`.
2. **Upscale small ROIs**: If ROI width or height &lt; 80 px, resize 2× before preprocessing and OCR.
3. **Config**: `ENABLE_LPR_PREPROCESS=1` (default) enables grayscale, CLAHE, adaptive threshold, and morph open before OCR; set to `0` to use raw ROI only.

---

### 2.6 Motion detection

**Current:** Frame diff with Gaussian blur, threshold 25, sum of binary &gt; 500.

**Research:**
- **Background subtraction**: MOG2 or KNN (OpenCV) with `detectShadows=true`, tuned `varThreshold`/`dist2Threshold`, and `history` reduce lighting false positives (OpenCV docs, Stack Overflow).
- **Morphology**: MORPH_OPEN on the foreground mask removes small noise; contour area filter (e.g. &gt; 300 px) drops tiny blobs.

**Improvements:**
1. **Optional MOG2/KNN**: Add `MOTION_BACKEND=mog2` (or `knn`) using `cv2.createBackgroundSubtractorMOG2(history=500, detectShadows=True)`; update background each frame; sum foreground pixels and compare to threshold.
2. **Morphology**: When using MOG2/KNN, apply MORPH_OPEN and filter contours by area before deciding “motion”.
3. **Configurable threshold**: `MOTION_THRESHOLD` already exists; document; consider per-camera or adaptive threshold (future).

---

### 2.7 Loitering and line crossing

**Current:** Zone ticks (person in polygon for N cycles); segment crossing of line by centroid movement.

**Research:**
- **Trajectory smoothing**: Centroid smoothing (e.g. moving average over 3–5 frames) reduces jitter and false line crosses (IEEE, trajectory-based loitering).
- **Time thresholds**: Calibrating “stay duration” and “escape time” improves precision/recall (e.g. PETS2007: 75% recall, 87% precision with tuned params) (Springer).
- **Tracking**: Associating the same person across frames (e.g. color + distance) improves loiter vs “different person re-entering” (Springer).

**Improvements:**
1. **Centroid smoothing**: Store last K centroids per “track” (e.g. by distance); use smoothed centroid for zone-in and line-cross tests.
2. **Config**: Expose `loiter_seconds` and crossing-line coords in UI; document calibration for different FOVs.
3. **Debounce line cross**: Require centroid to stay on opposite side for 1–2 cycles before firing to avoid flicker.

---

### 2.8 Extended attributes (height, build, hair, clothing, threat, anomaly)

**Current:** Heuristics from single frame and event; DeepFace age/gender on crop.

**Research:**
- **Height**: 170 cm at 450 px is camera-dependent; calibrate per camera or use known reference object (NIST, calibration docs).
- **DeepFace age/gender**: Optimal at 224×224 input; source resolution still matters (arXiv: impact of resolution on DeepFace/InsightFace). Face alignment improves age/gender.
- **Threat/anomaly**: Learned models (e.g. SPAN, temporal anomaly) outperform fixed heuristics; heuristics are a reasonable v1.

**Improvements:**
1. **Resize crop for DeepFace**: Ensure person/face crop is at least 224×224 (upscale if needed) before DeepFace.analyze(..., actions=['age','gender']).
2. **Height calibration**: Env or config `HEIGHT_REF_CM` and `HEIGHT_REF_PX` per camera for estimated_height_cm formula. **Implemented:** `HEIGHT_REF_CM` and `HEIGHT_REF_PX` in .env (see .env.example); app.py uses them when set (BEST_PATH_FORWARD Phase 2.4, STANDARDS_APPLIED). **HEIGHT_MIN_PX** (default 60): only compute estimated_height_cm when person bbox height ≥ this; reduces 120 cm outliers from tiny bboxes (DATA_QUALITY_IMPROVEMENTS_RESEARCH, IEEE 6233137).
3. **Detection confidence (NIST AI 100-4)**: **Implemented:** Per-row `detection_confidence` (YOLO confidence for primary person); in export, verify hash, and search. See DATA_POINT_ACCURACY_RATING §1.
4. **Document**: Add to EXTENDED_ATTRIBUTES.md the 224×224 recommendation and calibration.

---

### Demographic fairness (perceived_gender, perceived_age, perceived_ethnicity)

**perceived_gender**, **perceived_age** / **perceived_age_range**, and **perceived_ethnicity** are raw DeepFace outputs (no bucketing or gating). They are **not NIST FRVT-validated** and may exhibit **demographic differentials** (e.g. higher error rates for some skin tones or ages — NISTIR 8429, Gender Shades). For high-stakes identification, use an FRVT-validated engine or conduct an internal demographic audit. The app returns **face_attributes_note** in `GET /api/v1/what_we_collect` when extended attributes are on. See **DATA_POINT_ACCURACY_RATING.md** and **RESEARCH_MILITARY_CIVILIAN_ACADEMIC_LE.md** §4.

---

### 2.9 Audio (transcription, sentiment, emotion, stress, threat)

**Current:** Keyword-based sentiment/emotion/stress/threat from transcription; energy for anomaly.

**Research:**
- **ASR quality**: High WER hurts downstream emotion/sentiment; &lt;10% WER is a practical target (Deepgram, arXiv). Use best available ASR for your environment.
- **Multimodal fusion**: Text + acoustic features (prosody, energy) outperform text-only for emotion (arXiv, cross-modal SER).
- **Robustness to ASR errors**: Error-robust fusion and correction modules improve emotion accuracy when transcripts are noisy (arXiv).

**Improvements:**
1. **Improve ASR**: Prefer Google Cloud / Whisper / Deepgram when available; document WER vs latency trade-off.
2. **Acoustic features**: If raw audio or energy/duration is available, combine with text for stress/emotion (e.g. high energy + negative keywords → boost audio_stress_level).
3. **Keyword expansion**: Periodically review and extend _AUDIO_*_KEYWORDS from real incidents to improve recall (no code change; ops process).

---

### 2.10 Temporal consistency and event deduplication (implemented)

**Research:** Requiring agreement across frames reduces false positives (IEEE, trajectory and event detection). Deduplicating identical events within a short window avoids duplicate DB rows and alert fatigue.

**Implemented:**
1. **Temporal consistency**: The last 3 raw event outcomes (motion / loitering / line_cross / none) are stored in a deque. The emitted event is only set if at least 2 of the last 3 agree (majority vote). Otherwise the event is treated as none. This reduces flicker and one-frame false positives.
2. **Event deduplication**: Before inserting an event into the `events` table, the server checks whether the same `(event_type, camera_id)` was already inserted within the last 5 seconds. If so, the insert is skipped. This is controlled by `_LAST_EVENT_DEDUPE_SEC` and `_last_event_insert`.
3. **AI pipeline state**: The analysis loop updates a shared `_ai_pipeline_state` (current step, message, steps with detail and confidence). The UI can poll `/api/ai_pipeline_state` to show “how the AI is thinking” and which step (object_detection, pose, emotion, scene, motion, audio, fuse) last ran, improving interpretability.

---

### 2.10 WiFi (device_mac, OUI, probe_ssids)

**Current:** Scapy probe; OUI lookup; probe SSID parsing.

**Research:** Accuracy here is “presence/identity” not ML; completeness depends on capture window and parsing. No major ML-based improvement; document best practices (antenna placement, channel list).

---

## 3. Summary: high-impact, feasible improvements

| Priority | Area | Change | Status |
|----------|------|--------|--------|
| High | YOLO | YOLO_CONF and per-class filter; filter objects and crowd_count by conf | **Applied** |
| High | LPR | Preprocess ROI (grayscale, CLAHE, morph); upscale when ROI &lt; 80×24 px | **Applied** |
| Medium | Emotion | CLAHE when dark (EMOTION_CLAHE_THRESHOLD); min 48×48; 224×224 for age/gender | **Applied** |
| Medium | Motion | MOG2 + morphology (MOTION_BACKEND, MOTION_MOG2_VAR_THRESHOLD) | **Applied** |
| Medium | Loiter/line | Centroid smoothing (CENTROID_SMOOTHING_FRAMES); debounce line cross | **Applied** |
| Low | Scene | Lower-half mean + variance (SCENE_VAR_MAX_INDOOR) | **Applied** |
| Low | Pose | MediaPipe on person crop; Standing/Sitting/Walking from landmarks | **Applied** |
| Low | Audio | Fuse energy with text for stress; better ASR remains config | **Applied** (fusion) |
| Doc | All | Document in EXTENDED_ATTRIBUTES, DATA_COLLECTION_RESEARCH, STANDARDS_APPLIED | **Applied** |

---

## 4. References (abbreviated)

- Ultralytics YOLO: confidence thresholding, validation, imgsz (docs.ultralytics.com).
- FER: AVES preprocessing (Springer); face alignment and AMN (CVPR); resolution and preprocessing (ScienceDirect, Nature).
- LPR: Preprocessing for OCR (MDPI, arXiv); YOLO + preprocessing (Nature).
- Loitering: Trajectory analysis (IEEE); adaptive motion-state (Springer); centroid tracking (Springer).
- Motion: OpenCV MOG2/KNN, shadow detection, morphology (OpenCV, Stack Overflow).
- DeepFace/InsightFace: Resolution impact on age (arXiv).
- Speech emotion: ASR WER impact, multimodal fusion (arXiv); production sentiment (Deepgram).

Implementing the high-priority items (YOLO conf, LPR preprocessing) and documenting the rest in this file and in YOLO_INTEGRATION.md / EXTENDED_ATTRIBUTES.md will give the largest accuracy gains with minimal risk.

**See also:** [DATA_POINT_ACCURACY_RATING.md](DATA_POINT_ACCURACY_RATING.md) — each data point rated 1–100 with best-in-class improvements from military, law enforcement, and academic sources.
