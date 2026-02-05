# Vigil — Runbooks

Short procedures for common operational issues. See **README.md** and **docs/KEY_MANAGEMENT.md** for configuration and secrets.

---

## Lost camera / no signal

**Symptom**: Dashboard or Live shows "No signal" or "Offline" for a camera; stream is black or missing.

1. **Check source**: Confirm `CAMERA_SOURCES` in `.env` (index or RTSP URL). For RTSP, test the URL with VLC or `ffplay`.
2. **Restart streams**: Stop and start recording (Live view → toggle recording), or restart the app so cameras are re-opened.
3. **Hardware**: If using a USB camera, ensure it is connected and not in use by another process. On Linux, check `ls /dev/video*` and permissions.
4. **RTSP**: If using RTSP, check `RTSP_RECONNECT_SEC` and `RTSP_TIMEOUT_MS` in `.env`; increase timeouts for unstable networks.
5. **Logs**: Check application logs for OpenCV or RTSP errors when opening the feed.

---

## Export failed (403 / 500)

**Symptom**: Export data or recording download returns 403 or 500.

1. **403**: Export requires **operator** or **admin** role. Log in with an account that has the correct role; check Users & site access in Settings (admin).
2. **500**: Check disk space (Dashboard → System Status → Free space). If low, free space or increase retention pruning (`RETENTION_DAYS`). Check server logs for stack traces (e.g. file not found, permission error).

---

## Database locked / high CPU

**Symptom**: Requests hang or time out; logs show "database is locked" or SQLite errors; CPU is high.

1. **Single writer**: SQLite allows one writer at a time. Ensure only one Vigil instance is writing to `surveillance.db`; avoid sharing the DB file across hosts.
2. **Retention job**: The retention job runs periodically; if the DB is large, it can hold locks. Consider running retention during a maintenance window or increasing the interval.
3. **Backup during idle**: If backing up `surveillance.db`, use SQLite backup API or copy when the app is stopped to avoid lock contention.
4. **Scaling**: For high write load, consider moving to PostgreSQL (would require code changes); see **docs/ENTERPRISE_ROADMAP.md**.

---

## WebSocket not updating events

**Symptom**: New events appear in the database or API but the dashboard does not update in real time.

1. **Proxy**: Ensure the reverse proxy forwards WebSocket: Nginx needs `proxy_http_version 1.1` and `proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade";` for `/ws`.
2. **Flask**: Confirm `flask-sock` is installed (`pip install flask-sock`). Restart the app after installing.
3. **CORS**: If the frontend is on a different origin, ensure CORS allows the WebSocket origin; session cookie must be sent (same-site or CORS_ORIGIN).
4. **Redis**: If using multiple Flask workers/instances, set `REDIS_URL` so events are broadcast via Redis pub/sub; otherwise only the instance that received the event will push to its clients.

---

## Time / NTP (evidence integrity)

**Symptom**: Export timestamps are wrong or health check reports `time_sync_status: unknown`.

1. **System time**: Ensure the host is using NTP (e.g. `timedatectl` on Linux, or enable Windows time sync). Incorrect time affects audit logs and export chain of custody.
2. **Readiness**: `GET /health/ready` returns `time_sync_status: synced` when `ntplib` is installed and the offset to pool.ntp.org is under 5 seconds. Install with `pip install ntplib` for optional NTP check.
3. **Evidence**: For legal or insurance exports, document that the system was time-synced at export time; use the `X-Export-UTC` header on exports.

---

## Low disk space

**Symptom**: Dashboard shows "Low disk space" warning; recordings or exports fail.

1. **Free space**: Dashboard System Status shows **Free** (free space on the recordings drive). Free up disk space on that volume (delete old files, move recordings to another drive).
2. **Retention**: Set **`RETENTION_DAYS`** in `.env` so the retention job deletes old `ai_data`, events, and `recording_*.avi` files. Restart the app if you change it.
3. **Storage path**: Change where recordings are stored via Settings → Storage (or `RECORDINGS_DIR` / storage API) to a drive with more space.
4. **Legal hold**: Items under legal hold are excluded from retention; remove holds if no longer needed so they can be pruned.

---

## Evidence and export (OSAC / production)

**Applied standards:** [BEST_PATH_FORWARD_HIGHEST_STANDARDS.md](BEST_PATH_FORWARD_HIGHEST_STANDARDS.md), [RESEARCH_MILITARY_CIVILIAN_ACADEMIC_LE.md](RESEARCH_MILITARY_CIVILIAN_ACADEMIC_LE.md).

1. **Primary vs working image (OSAC 2024-N-0011; Phase 3.7):** The **primary image** is the first recording to media (the AVI/MP4 file written while recording). An **export** of that file or of AI data is a **working image** (copy for analysis/sharing). Retain the primary or a verified backup; use working copies for distribution. **Manifest fields:** `GET /recordings/<filename>/manifest` returns `image_type: 'primary'` for the stored file; incident_bundle manifest returns `image_type: 'working'`. The incident_bundle also includes preservation_checklist and collection_checklist for chain of custody.
2. **Fixity:** With **ENABLE_RECORDING_FIXITY=1**, a background job computes SHA-256 of recordings and compares to stored values; manifest includes fixity status. Ensures integrity (OSAC/SWGDE).
3. **Production HTTPS (Phase 3.2):** Set **ENFORCE_HTTPS=1** to redirect HTTP to HTTPS; or **ENFORCE_HTTPS=reject** to return 403 for non-HTTPS (no redirect). Run behind a TLS-terminating reverse proxy; set `X-Forwarded-Proto: https` so the app sees the request as secure. Required for CJIS/NIST-style production.

---

## Legal hold workflow (Phase 3.3)

**Purpose:** Preserve specific recordings or events from retention deletion (NIST IR 8387 / SWGDE). Operator/admin can place a hold; retention job skips held items.

1. **List holds:** `GET /api/v1/legal_hold` (operator/admin). Returns `holds`: list of `{ id, resource_type, resource_id, held_at, held_by, reason }`.
2. **Place hold:** `POST /api/v1/legal_hold` with JSON `{ "resource_type": "recording"|"event", "resource_id": "<filename or event id>", "reason": "optional" }`. Use recording filename (e.g. `recording_0_20260205.avi`) or event id. Returns `{ id, resource_type, resource_id, held_at, held_by }` or 200 with `message: "Already held"`.
3. **Remove hold:** `DELETE /api/v1/legal_hold/<hold_id>` (admin only). After removal, the item becomes subject to retention again.
4. **Retention:** The retention job does not delete recordings whose filename is in `legal_hold` (resource_type='recording') or events whose id is in `legal_hold` (resource_type='event'). Export and incident_bundle are unchanged; held items remain available for export until hold is removed and retention runs.

**UI:** Settings or Export page can call these APIs to list holds, add hold (e.g. from a recording or event row), and remove hold (admin). See **docs/STANDARDS_APPLIED.md** and **BEST_PATH_FORWARD_HIGHEST_STANDARDS.md** Phase 3.3.

---

## Export certificate (optional, Phase 3.5)

**Purpose:** For high-assurance or LE use, retain the export manifest and verify hashes (SWGDE 23-V-001).

1. **Current:** Export responses include `X-Export-SHA256` and `X-Export-UTC`; incident_bundle manifest includes preservation_checklist with per-item SHA-256. Verify ai_data integrity via `GET /api/v1/ai_data/verify`.
2. **Retention:** Store the manifest JSON (and, if used, the exported file) with the same care as the primary recording; document operator and export time for chain of custody.
3. **Optional future:** Signed manifest (digital signature over manifest JSON) or dual-hash (SHA-256 + SHA3-256) for maximum assurance; see **docs/KEY_MANAGEMENT.md** § Export manifest signing.

---

## Encryption at rest (Phase 3.1)

**Purpose:** Meet CJIS/FIPS/ISO expectations for encryption of DB and recordings at rest. Vigil does not implement app-level encryption; use volume or directory encryption.

1. **Linux (LUKS):** Create an encrypted volume and mount it for Vigil data. Example: create a LUKS partition or loop file, format, mount at e.g. `/mnt/vigil_data`. Set **DATA_DIR**=/mnt/vigil_data (or use it as app directory) so `surveillance.db` and, if desired, **RECORDINGS_DIR** point inside the mount. Unlock at boot (key file or TPM) and document key lifecycle.
2. **Windows:** Use BitLocker on the drive or volume that holds the app directory (or DATA_DIR and RECORDINGS_DIR).
3. **Cloud / VM:** Use provider encryption (e.g. encrypted EBS volume, encrypted disk). Ensure the volume that contains `surveillance.db` and recordings is encrypted at rest.
4. **Key lifecycle:** Document where the encryption key is stored, who can access it, and rotation procedure; see **docs/KEY_MANAGEMENT.md**.

App-level encryption (optional future) would use env or vault for keys; see KEY_MANAGEMENT.md § Encryption at rest.

---

## Runbook index

| Issue | Section |
|-------|---------|
| Lost camera / no signal | Above |
| Export failed (403 / 500) | Above |
| Database locked / high CPU | Above |
| WebSocket not updating | Above |
| Time / NTP | Above |
| Low disk space | Above |
| Evidence and export (OSAC / production) | Above |
| Legal hold workflow | Above |
| Export certificate (optional) | Above |
| Encryption at rest | Above |

For more troubleshooting, see **README.md § Troubleshooting** and **docs/INSTALL_AUDIT.md**.
