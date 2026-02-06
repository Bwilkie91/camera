# Extended Detection Attributes & Sci-Fi Roadmap

This document describes the **extended person and behavior attributes** added to the AI detection pipeline: demographic proxies (optional), physical descriptors, behavioral flags, intoxication/drug stubs, and "sci-fi" style scores. It also outlines research-backed future additions for maximum power and accuracy.

---

## 1. Data Points Implemented

### 1.1 Physical / appearance (speed-optimized)

| Field | Source | Notes |
|-------|--------|--------|
| **estimated_height_cm** | Person bbox height vs reference scale | 120–220 cm clamp. Assumes ~170 cm at ~450 px; tune per camera. |
| **build** | Bbox aspect ratio (width/height) | slim / medium / heavy. |
| **hair_color** | Dominant color in top 25% of person ROI | black, white, red, blue, green, brown, gray, unknown. |
| **clothing_description** | Dominant color in lower 2/3 body ROI | e.g. "blue top/body". |

### 1.2 Demographic proxies (raw data; no bias engineering)

| Field | Source | Notes |
|-------|--------|--------|
| **perceived_gender** | DeepFace `dominant_gender` on person crop | Raw model output. Requires `ENABLE_EXTENDED_ATTRIBUTES=1`. Crop 224×224. |
| **perceived_age** | DeepFace `age` (integer) | Raw estimated age in years. New column for numeric use. |
| **perceived_age_range** | Same `age` as string | Raw age as string (e.g. `"34"`), no bucketing. |
| **perceived_ethnicity** | DeepFace `dominant_race` | Raw model output; always stored when extended attributes are on (no gating). |

- **ENABLE_EXTENDED_ATTRIBUTES** (default `1`): Enables DeepFace age/gender/race and all heuristics. No bucketing or legal gating; civilian-only raw demographics.
- **FRVT / demographic fairness:** These are model outputs, not NIST FRVT-validated. See **ACCURACY_RESEARCH_AND_IMPROVEMENTS.md** and **DATA_POINT_ACCURACY_RATING.md**.

### 1.3 Behavioral and intent

| Field | Source | Values |
|-------|--------|--------|
| **suspicious_behavior** | Derived from event | none / loitering / line_crossing / person_down (Fall Detected). |
| **predicted_intent** | Derived from event and pose | passing / loitering / crossing / standing / fall_or_collapse / unknown. When event is None: standing (if pose Standing), unknown otherwise. Fall → fall_or_collapse. |
| **stress_level** | Emotion → stress proxy | high (Angry, Fear, Sad, Disgust), medium (Surprise), low (Neutral, Happy). |
| **anomaly_score** | Heuristic | 0.0 (normal), 0.5 (loiter), 0.6 (line_cross), 0.7 (fall). |
| **threat_score** | Heuristic 0–100 | Base 0; +25 suspicious, +25 person_down, +20 high stress, +15 loiter, +10 line_cross (BEST_PATH Phase 2.3). |

### 1.4 Intoxication / drug / gait (stubs)

| Field | Current | Future |
|-------|--------|--------|
| **intoxication_indicator** | Always `none` | Gait model (unsteady, sway) or bilinear CNN on gait clips. |
| **drug_use_indicator** | Always `none` | Behavioral/pose cues or dedicated model. |
| **gait_notes** | From pose landmarks when available (posture + symmetry) | Temporal pose buffer → stride, cadence, limping. See **docs/GAIT_AND_POSE_OPEN_SOURCE.md**. |

Research: Gait-based intoxication detection (bilinear CNN, deep gait) and phone/wearable sensors show high correlation with eBAC; video-based systems exist but need temporal windows.

### 1.5 Scene / context (no extra inference)

| Field | Source | Values |
|-------|--------|--------|
| **illumination_band** | Frame mean brightness | dark (&lt;80) / dim (80–120) / normal (120–180) / bright. |
| **period_of_day_utc** | UTC hour at detection | night (0–5, 21–24) / dawn (5–7) / day (7–17) / dusk (17–21). |

### 1.6 Sci-fi style fields (extensible)

| Field | Current | Future |
|-------|--------|--------|
| **micro_expression** | Same as dominant emotion | Dedicated MER model (CASME, MEGC) for concealed emotion. |
| **attention_region** | Person position in frame from bbox center | left/center/right, top/middle/bottom (e.g. `center,middle`). Future: gaze model. |
| **threat_score** | Heuristic (includes +25 for person_down) | Learned model (e.g. SPAN, DeepUSEvision) for continuous suspicion. |
| **anomaly_score** | Event-based | Temporal anomaly detection (HTSNet, transformer fusion). |

### 1.7 Audio (same intensity as visual)

Extended audio analysis runs in parallel with visual: one capture returns transcription plus energy and duration, then **audio attributes** are derived at the same level of intensity as the visual pipeline.

| Field | Source | Notes |
|-------|--------|--------|
| **audio_transcription** | Speech-to-text (Google / recognizer) | Same as legacy `audio_event`; also stored here for clarity. |
| **audio_sentiment** | Keyword matching | positive / negative / neutral / threat. |
| **audio_emotion** | Keyword sets | angry, sad, happy, fear, calm, distress, neutral. |
| **audio_stress_level** | Keywords + threat count | low / medium / high. |
| **audio_threat_score** | Threat keywords | 0–100. |
| **audio_anomaly_score** | Energy + threat | 0.0–0.7 (loud/quiet or threat keywords). |
| **audio_energy_db** | RMS of raw buffer → dB | Approximate loudness. |
| **audio_background_type** | Heuristic | silence / speech / quiet_speech / loud_speech_or_noise. |
| **audio_speech_rate** | words / (duration_sec/60) | Words per minute. |
| **audio_language** | Stub | e.g. `en`. |
| **audio_keywords** | Extracted threat/emotion terms | Comma-separated, for search. |
| **audio_speaker_gender** | Stub | For future voice attribute model. |
| **audio_speaker_age_range** | Stub | For future voice attribute model. |
| **audio_intoxication_indicator** | Stub | For future slur/tempo model. |

Threat/negative/stress keyword sets are defined in `app.py` (`_AUDIO_THREAT_KEYWORDS`, `_AUDIO_NEGATIVE_KEYWORDS`, `_AUDIO_STRESS_KEYWORDS`, etc.). Search (`POST /api/v1/search`) includes `audio_event`, `audio_transcription`, `audio_sentiment`, `audio_emotion`, `audio_stress_level`, `audio_keywords`. Activity log and event metadata include the main audio fields.

---

## 2. Database and API

- **Table**: `ai_data`. New columns added via migration in `_init_schema()`.
- **Hash**: `_AI_DATA_HASH_ORDER` includes all new fields for chain-of-custody integrity.
- **Export**: CSV export includes all columns (`SELECT *`).
- **Search**: `POST /api/v1/search` searches across: object, event, scene, license_plate, suspicious_behavior, predicted_intent, stress_level, hair_color, build, perceived_gender, perceived_age_range, perceived_age, perceived_ethnicity, clothing_description, gait_notes, intoxication_indicator, micro_expression.

---

## 3. Speed and Accuracy

- **Single DeepFace call** when extended attributes are on: one `analyze(crop, actions=['age','gender'])` (and optionally `'race'`) per frame to avoid slowdown.
- **Heuristics** use existing YOLO bbox and pose/emotion; no extra model runs for build, height, hair, clothing, stress, intent, threat, anomaly.
- **Crop**: Person bbox (with padding) is used for DeepFace and color regions to improve accuracy and speed.

For higher accuracy later:

- Use a dedicated **person attribute model** (e.g. CLEAR, PETA, RAP) for hair, clothing, and demographics in one forward pass.
- Add **temporal smoothing** (e.g. running average of age/gender over N frames) to reduce flicker.
- **Gait**: Maintain a short pose/gait buffer (e.g. 1–2 s) and run a small temporal model for intoxication/gait notes.

---

## 4. Sci-Fi Level Additions (research-backed)

These are feasible next steps from current literature; not all implemented yet.

| Addition | Research / tech | Notes |
|----------|------------------|--------|
| **Micro-expression recognition** | MEGC, CASME II, Spot-Then-Recognize | Detects concealed emotion; high-stakes and cross-cultural datasets. |
| **Stress from video** | Facial emotion + rPPG (Eulerian magnification), SympCam-style 3D CNN | Contactless stress/arousal; 90%+ balanced accuracy in studies. |
| **Gait-based intoxication** | Bilinear CNN on gait, deep learning on pose sequences | Fine-grained intoxicated gait classification from video. |
| **Continuous suspicion / intent** | SPAN (suspicion progression), DeepUSEvision (object + face + body + fusion) | Earlier detection, explainable scores. |
| **Attention / gaze** | Gaze estimation (L2CS-Net, etc.) | attention_region = where the person is looking. |
| **Remote heart rate (rPPG)** | Eulerian Video Magnification, EVM + filtering | Stress/arousal proxy; 5–6 BPM MAE in some setups. |
| **Abnormal behavior in crowds** | Hybrid temporal-spatial nets, transformer fusion | Anomaly score from scene-level model. |
| **Clothing-invariant ReID** | Color disentanglement, pose-guided supervision | Stable identity across clothing change for tracking. |

---

## 5. UI and Labels

- **Activity log** (Flask): Table includes Time, Event, Object, Emotion, Pose, Scene, Crowd, Plate, Camera, **Stress, Build, Hair, Intent, Suspicious, Threat, Height, Age, Gender** (horizontal scroll on small screens).
- **Timeline / Events**: Event metadata includes extended fields (suspicious_behavior, predicted_intent, stress_level, threat_score, anomaly_score, build, hair_color, estimated_height_cm, perceived_age, perceived_age_range, perceived_gender, perceived_ethnicity) in expandable detail and JSON.
- **Frontend labels**: `frontend/src/labels.ts` defines `EXTENDED_ATTRIBUTE_LABELS` and `EXTENDED_ATTRIBUTE_DESCRIPTIONS` for consistent tooltips and filters.

---

## 6. Compliance and Ethics

- **Demographics**: Age, gender, and ethnicity are stored as raw model output (no bucketing or gating). Civilian-only; operator is responsible for lawful use and retention.
- **Intoxication/drug**: Stubs only; do not use for enforcement without validated, legally approved systems and policies.

Implementations follow a single DeepFace call per frame for speed, heuristics for the rest, and clear stubs and docs for future sci-fi upgrades (gait, MER, gaze, rPPG, continuous suspicion).

---

## 7. See also

- **docs/IDENTITY_MARKERS_AND_REID.md** — Research on effective markers to identify or re-identify individuals using AI (soft biometrics, clothing/accessories, gait), mapping to current schema and recording recommendations.
