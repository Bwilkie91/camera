# Notable Behavior Screenshots

The system automatically captures and logs **notable behavior screenshots** when certain human behaviors or situations are detected. Each capture is stored on disk and recorded in the database with a **reason** and **reason_detail** so operators can review why the screenshot was taken.

## Why log the reason?

- **Auditability**: Security and compliance require knowing why a given image was retained.
- **Review efficiency**: Operators can filter by reason (e.g. only loitering, or only high threat).
- **Research alignment**: Reasons are tied to documented behavioral indicators used in VMS and security literature.

## Behaviors and situations we detect (research-based)

Detection is based on established security and VMS (Video Management System) practice and behavioral research:

| Reason slug | When we capture | Research / rationale |
|-------------|------------------|----------------------|
| **loitering** | Loitering Detected (person remained in zone beyond threshold) | Primary indicator in CCTV; often precedes theft, vandalism, or unauthorized access; effective in retail, transport, 24/7 sites. |
| **line_crossing** | Virtual line crossing (perimeter/rule violation) | Standard VMS rule; used for perimeter and access control. |
| **elevated_threat** | `threat_score` ≥ threshold (default 50) | Combines visual/behavioral cues; security-relevant escalation. |
| **high_stress_negative_emotion** | High stress + negative emotion (Angry, Fear, Sad, Disgust) | Body movement and physiological state; potential distress or aggression. |
| **audio_threat** | `audio_threat_score` ≥ threshold | Verbal tone, distress keywords, or threat language in audio. |
| **behavioral_anomaly** | `anomaly_score` ≥ 0.5 | Deviation from normal activity; loiter/line cross or movement anomaly. |
| **crowding** | `crowd_count` ≥ threshold (default 5) | Safety and capacity; crowd-related risk. |
| **suspicious_behavior** | Non-empty `suspicious_behavior` (e.g. fidgeting, pacing) | Observable behavioral indicators; anomalous behavior in context. |

### Broader behavioral context (research)

Security and behavioral detection literature emphasizes:

- **Communication patterns** – verbal and non-verbal interactions.
- **Pattern-of-life data** – routine vs. deviation (e.g. standing still, repeated passes, unusual trajectories).
- **Body movement and physiological state** – movement, facial expression, voice tone.

No single cue is reliable on its own; the system uses multiple signals (motion, loitering, line crossing, threat/stress/anomaly scores, audio, crowd count) and logs the **reason** and **reason_detail** for each screenshot so reviewers can understand the context.

## Configuration

- **`NOTABLE_SCREENSHOTS_DIR`** – Directory where JPEGs are saved (default: `notable_screenshots` next to the app).
- **`NOTABLE_COOLDOWN_SECONDS`** – Per-reason cooldown between captures (default: 60).
- **`NOTABLE_CROWD_THRESHOLD`** – Crowd count above which we capture for “crowding” (default: 5).
- **`NOTABLE_THREAT_THRESHOLD`** – Minimum threat score for “elevated_threat” and “audio_threat” (default: 50).

## Database

Table: **`notable_screenshots`**

- `id`, `timestamp_utc`, `reason`, `reason_detail`, `file_path`, `camera_id`, `event_id`, `created_at`

Screenshots are taken during the main `analyze_frame` loop when `_is_notable_behavior` returns a reason and the per-reason cooldown has expired.

## API

- **`GET /api/v1/notable_screenshots`**  
  List entries. Query params: `limit` (default 50, max 200), `camera_id`, `reason`, `since` (ISO date or datetime).

- **`GET /api/v1/notable_screenshots/<id>/image`**  
  Serve the JPEG for a given notable screenshot `id`.

Response shape for list: `{ "notable_screenshots": [ { "id", "timestamp_utc", "reason", "reason_detail", "file_path", "camera_id", "event_id", "created_at" }, ... ] }`.

## References

- RAND: *Using Behavioral Indicators to Help Detect Potential Violent Acts* (communication patterns, pattern-of-life, body movement).
- Loitering detection in CCTV (retail, warehouses, transport hubs).
- Classification of normal vs. suspicious behaviour at access points (solo vs. group patterns).
