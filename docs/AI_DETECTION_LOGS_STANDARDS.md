# AI Detection Logs — Standards Alignment

Vigil’s AI detection and event logging is aligned with **government and academic best practices** for video analytics metadata, chain of custody, and digital evidence. This document summarizes the standards used and how they are applied.

---

## Reference Standards

| Source | Scope | Relevance |
|--------|--------|-----------|
| **NISTIR 8161 (Rev. 1)** | CCTV Digital Video Export Profile (NIST/FBI) | UTC timestamps, equipment/system identification, metadata for video analytics, chain of custody and data integrity (digital signature / hash). |
| **NIST Digital Video Exchange Standards** | NIST Video Analytics / DMSAC | Standardized export formats, frame-accurate time, prevention of metadata loss. |
| **SWGDE** (Scientific Working Group on Digital Evidence) | Best Practices for Digital Video Authentication (e.g. 23-V-001) | Authentication, chain of custody, documentation of acquisition and provenance. |
| **NIST AI 100-4** | Digital Content Transparency / Synthetic Content | Provenance of AI-generated or AI-assisted content; recording of model/source. |
| **CJIS Security Policy** | Criminal Justice Information Services | Audit, access control, and integrity requirements for systems handling CJI. |
| **IEC 62676-2-32 / ONVIF** | Video surveillance recording and export | Export file format, metadata, and integrity (referenced by NISTIR 8161). |

---

## Implemented Capabilities

### 1. UTC timestamps (NISTIR 8161, SWGDE)

- **ai_data**: Each detection row has `timestamp_utc` (ISO 8601 UTC, e.g. `2026-02-04T14:30:00Z`) in addition to local `date`/`time`.
- **events**: Each event has `timestamp_utc` and server `timestamp` for correlation and export.
- **Exports**: CSV export header includes `# Export UTC: …` and response header `X-Export-UTC` for evidence documentation.

### 2. Equipment and system identification (NISTIR 8161)

- **system_id**: Stored per detection row and in export metadata. Set via env `SYSTEM_ID` or hostname (`platform.node()`), fallback `vigil`.
- **Export**: `# System: {system_id}` in CSV and `X-System-ID` response header.
- **Operator**: Export records operator (logged-in user) in `# Operator: …` and `X-Operator` header for chain of custody.

### 3. AI model provenance (NIST AI 100-4)

- **model_version**: Each ai_data row records the detection model identifier (e.g. `YOLO_MODEL` env value, default `yolov8n.pt`).
- Supports reproducibility and disclosure of “AI-assisted” detection in exports and audits.

### 4. Per-row integrity (chain of custody)

- **ai_data**: `integrity_hash` column stores SHA-256 over a canonical payload of the row (timestamp_utc, date, time, camera_id, system_id, model_version, event, object, and other detection fields). Enables verification that rows have not been altered.
- **events**: `integrity_hash` stores SHA-256 over (timestamp_utc, event_type, camera_id, site_id, metadata, severity).
- **Verification**: `GET /api/v1/ai_data/verify` (operator/admin) recomputes hashes and returns `verified` / `mismatched` / `total` for rows that have an integrity_hash.

### 5. Export integrity (NISTIR 8161 / SWGDE)

- **CSV export**: Full export content (metadata header + column headers + body) is hashed with SHA-256; hash appears in CSV footer (`# SHA-256: …`) and in response header `X-Export-SHA256`.
- **Response headers**: `X-Export-UTC`, `X-Operator`, `X-System-ID`, `X-Export-SHA256` support chain-of-custody documentation and verification.

### 6. Audit and retention

- Export and verification actions are audited (e.g. `export_data`, resource `ai_data`).
- Retention job respects `RETENTION_DAYS` for ai_data and events; audit log has separate `AUDIT_RETENTION_DAYS` (AU-9).

---

## Schema Additions (migrations)

- **ai_data**: `timestamp_utc`, `model_version`, `system_id`, `integrity_hash`.
- **events**: `timestamp_utc`, `integrity_hash`.
- Index: `idx_ai_data_timestamp_utc` for time-range queries and retention.

Existing rows may have NULL for new columns; new inserts from the analysis loop and from `POST /events` populate them.

---

## Configuration

| Item | Env / location | Description |
|------|----------------|-------------|
| **System identifier** | `SYSTEM_ID` | Equipment/system ID for chain of custody; default hostname or `vigil`. |
| **Model identifier** | `YOLO_MODEL` or `YOLO_WEIGHTS` | Stored as `model_version` in each ai_data row (e.g. `yolov8n.pt`). |

---

## API Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /get_data` | GET | Returns ai_data including `timestamp_utc`, `model_version`, `system_id`, `integrity_hash` when present. |
| `GET /events` | GET | Returns events including `timestamp_utc`, `integrity_hash`. |
| `GET /export_data` | GET | CSV export with metadata header, SHA-256 footer, and headers `X-Export-SHA256`, `X-Export-UTC`, `X-Operator`, `X-System-ID`. |
| `GET /api/v1/ai_data/verify` | GET | Recomputes integrity_hash for ai_data rows and returns verified/mismatched/total (operator/admin). |

---

## References

- NIST, *Recommendation: CCTV Digital Video Export Profile - Level 0 (Revision 1)*, NISTIR 8161 rev1 (2019).  
  [https://www.nist.gov/publications/recommendation-closed-circuit-television-cctv-digital-video-export-profile-level-0](https://www.nist.gov/publications/recommendation-closed-circuit-television-cctv-digital-video-export-profile-level-0)
- NIST, Digital Video Exchange Standards: [https://www.nist.gov/programs-projects/digital-video-exchange-standards](https://www.nist.gov/programs-projects/digital-video-exchange-standards)
- SWGDE, Best Practices for Digital Video Authentication (23-V-001): [https://www.swgde.org/23-v-001/](https://www.swgde.org/23-v-001/)
- NIST AI 100-4 (digital content transparency / synthetic content detection and provenance).

See also **GOVERNMENT_STANDARDS_AUDIT.md** and **README.md** for video export (recordings) and audit log integrity.
