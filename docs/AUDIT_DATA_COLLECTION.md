# Data collection & chain-of-custody audit

This document rates and describes how kVigil collects AI detections and events, applies integrity hashes (NISTIR 8161–style chain of custody), and logs speech when audio is enabled.

---

## 1. AI detections and events only while recording is on

**Rating: 5/5 — Correct and well gated**

- **AI pipeline** (`analyze_frame()` in `app.py`): The entire analysis loop runs only when `is_recording` is true. When recording is off, the loop only sleeps and optionally flushes any buffered `ai_data` to the database; no new frames are read, no YOLO/pose/emotion/scene/motion/audio runs, and no new rows are appended to `ai_data` or `events`.
- **Video recording**: Frames are written to the current AVI file only inside `gen_frames()` when `is_recording` is true (`if is_recording:` before `out.write(rec_frame)`).
- **Recording config** (`/recording_config`): Docstring states *"Data is collected only while recording is on."* Event types, `capture_audio`, `capture_thermal`, `capture_wifi`, and `ai_detail` only affect what is *included* in data that is already gated by recording.

**Conclusion:** AI detections and events are collected only while recording is on. No enhancement needed for this requirement.

---

## 2. Exports and recordings use integrity hashes (NISTIR 8161–style chain of custody)

**Rating: 5/5 — Implemented end-to-end**

### Per-row integrity (database)

- **ai_data**: Each row gets `integrity_hash` = SHA-256 over a canonical string of selected fields (see `_AI_DATA_HASH_ORDER`). Computed in `_ai_data_integrity_hash()`; stored on INSERT. Verification: `GET /api/v1/ai_data/verify` (returns verified/mismatched/total).
- **events**: Each row gets `integrity_hash` = SHA-256 over `(timestamp_utc, event_type, camera_id, site_id, metadata, severity)` in `_event_integrity_hash()`. Stored on INSERT; returned in event list and detail APIs.
- **audit_log**: Rows can have `integrity_hash`; audit export includes it. Verification: `GET /audit_log/verify`.

### Export-level integrity (NISTIR 8161 / SWGDE)

- **AI data CSV export** (`/api/v1/export` or equivalent): CSV includes a footer `# SHA-256: <hash>` where the hash is over the entire export (metadata + headers + body). Response headers: `X-Export-SHA256`, `X-Export-UTC`, `X-Operator`, `X-System-ID`. The CSV also includes a per-row `integrity_hash` column for row-level verification.
- **Recordings**: Export uses `_export_recording_file()` which computes SHA-256 of the file (or the converted MP4). Response headers include `X-Export-SHA256`, `X-Operator`, `X-System-ID`, `X-Camera-ID`. Manifest: `GET /recordings/<name>/manifest` returns `sha256`, `system_id`, `camera_id`, `size_bytes`, `created_utc`.
- **Audit log CSV export**: Export includes `# SHA-256: <hash>` and `X-Export-SHA256` header.

**Conclusion:** Exports and recordings use NISTIR 8161–style chain of custody (per-row hashes where applicable, export/file-level SHA-256, operator and system identifiers). Verification endpoints exist for ai_data and audit_log.

---

## 3. Speech from microphone transcribed and logged when audio is enabled

**Rating: 5/5 — Correct when recording + audio are on**

- **Transcription**: When `ENABLE_AUDIO=1` and the UI has “Audio” on (`_audio_capture_enabled`), the audio worker thread (`_audio_worker_loop()`) listens via PyAudio/SpeechRecognition and calls `recognize_google()`. The result is stored in `audio_result` (dict with `text`, `energy_db`, `duration_sec`).
- **Logging**: The analyze pipeline reads the latest result via `get_audio_event()` only when **recording is on**. It then:
  - Maps transcription into `audio_event` and extended fields via `_extract_audio_attributes()` (e.g. `audio_transcription`, `audio_sentiment`, `audio_emotion`, `audio_energy_db`).
  - Writes these into the `data` dict that is appended to `_ai_data_batch` and later inserted into `ai_data`. So speech is **logged to the database only when recording is on and** (via `recording_config`) **capture_audio is true**.
- If **capture_audio** is false in recording config, the pipeline does not persist speech (audio fields are set to `'None'`/null). The audio worker can still run for live UI display, but we skip calling `get_audio_event()` when `capture_audio` is false for efficiency (see code).

**Conclusion:** Speech is transcribed and logged when audio is enabled and recording is on (and capture_audio is true). Behavior matches the requirement.

---

## Efficiency and performance

- **AI pipeline**: One thread (`analyze_frame`); interval configurable via `ANALYZE_INTERVAL_SECONDS` (default 10s; range 5–60). Batch inserts: up to `AI_DATA_BATCH_SIZE` rows (default 10, max 50) then a single commit to reduce DB contention.
- **get_data / events**: Capped at 1000 rows per request; `ai_data` and `events` have indexes on `timestamp_utc` (and date/time, camera_id, site_id) for fast ORDER BY and filters. ETag on `get_data` for 304 Not Modified.
- **Audio**: When recording config has `capture_audio: false`, the analyze loop skips `get_audio_event()` and uses fixed “None” attributes so no microphone or Google API call is made for that cycle.
- **Exports**: CSV generated in memory; recording export streams file with SHA-256 computed in chunks (64 KB). No unnecessary full-table scans beyond the export query.

---

## Summary table

| Area | Rating | Notes |
|------|--------|--------|
| AI/events only when recording on | 5/5 | Single gate `is_recording`; video and pipeline both gated. |
| Integrity hashes (NISTIR 8161) | 5/5 | Per-row hashes for ai_data/events/audit; export/file SHA-256 + headers; verify APIs. |
| Speech transcribed & logged when audio on | 5/5 | Transcribed in worker; logged to ai_data only when recording on + capture_audio. |
| Data flow efficiency | 5/5 | Batch commits, indexes, ETag, optional audio skip when capture_audio off. |
