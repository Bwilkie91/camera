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

## Runbook index

| Issue | Section |
|-------|---------|
| Lost camera / no signal | Above |
| Export failed (403 / 500) | Above |
| Database locked / high CPU | Above |
| WebSocket not updating | Above |
| Time / NTP | Above |
| Low disk space | Above |

For more troubleshooting, see **README.md § Troubleshooting** and **docs/INSTALL_AUDIT.md**.
