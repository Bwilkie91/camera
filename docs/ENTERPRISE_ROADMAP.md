# Enterprise & Next-Gen Surveillance Roadmap

Research-backed comparison and roadmap to bring this VMS to best-in-class performance, AI/ML features, and scalability.

---

## 1. Best-in-Class Reference (2024–2025)

### Enterprise VMS Feature Set

| Domain | Best-in-class (e.g. Milestone, Genetec, NVIDIA Metropolis) | This system (current) | Target |
|--------|-------------------------------------------------------------|------------------------|--------|
| **Cameras per site** | 100–1000+ with tiered hosting/media/control | Single-node, multi-camera via env | Multi-site, configurable per-node limits |
| **AI/ML analytics** | Object detection, face/vehicle, behavior, NL search, summarization | YOLO, LPR, motion, loiter, line-cross | + Heatmaps, NL search hook, optional LLM summarization |
| **Streaming** | MJPEG, HLS, WebRTC, low-latency edge | MJPEG, multi-camera | Add HLS/WebRTC gateway option for scale |
| **Search** | Keyword + semantic / natural language over video | Filter by date, event_type, camera | API for NL/search and heatmap aggregates |
| **Multi-tenancy** | Sites, tenants, RBAC per resource | Sites/cameras, **resource-level RBAC** (user_site_roles) | site_id on event/data APIs; GET/PUT /api/v1/users/<id>/sites; optional tenant auth later |
| **Scale-out** | K8s, microservices (hosting/web/control/media) | Monolith, single process | API versioning, health probes, optional Redis, Docker/K8s path |
| **Audit & compliance** | NIST/CJIS-style, chain of custody, retention | Audit log, retention job, NISTIR-style export metadata | Per GOVERNMENT_STANDARDS_AUDIT.md |

### Next-Gen AI/ML (Research Summary)

- **Natural language video search**: Query by intent (“person in red shirt”, “white SUV”) via embeddings + LLM (e.g. NVIDIA AI Blueprint, VLMs). *This codebase: search API stub and keyword/semantic extension point.*
- **Video summarization**: LLM-based summarization of long clips (CVPR 2024/2025). *This codebase: webhook/plugin for external summarization service.*
- **Multi-camera tracking**: Re-ID and tracking across cameras (NVIDIA multi-camera workflow). *This codebase: camera_id and site_id consistently; future: Re-ID pipeline.*
- **Edge vs cloud**: Edge (Jetson/DeepStream) for real-time detection; cloud for heavy NL/summarization. *This codebase: single-node analytics; design allows pluggable “analytics backend” (local vs remote).*
- **Behavior & heatmaps**: Dwell time, people count per zone, heatmaps over time. *This codebase: zone-based loitering; add heatmap/aggregate API.*

---

## 2. Scalability Path

### Phase A – Single node (current + enhancements)

- **API versioning**: All data/control APIs under `/api/v1/` so v2 can coexist.
- **Health**: `/health` (liveness), `/health/ready` (readiness: DB + cameras optional).
- **Tenant/site**: `site_id` on events and in APIs; filter get_data/events by site/camera.
- **Analytics API**: Heatmap/counts by zone and time bucket; search endpoint (keyword + future NL).

### Phase B – Multi-instance ready

- **Stateless API**: Session in signed cookie or external store; no in-memory-only state for auth.
- **Event broadcast**: Optional Redis pub/sub for WebSocket so all instances push same events.
- **Config**: `REDIS_URL`, `API_VERSION_PREFIX`, `MAX_CAMERAS_PER_NODE`.

### Phase C – Multi-node / Kubernetes

- **Deployment**: Dockerfile; Helm or K8s manifests (optional).
- **Services**: API pods (scale replicas); optional separate “analytics worker” pods that pull from queue or shared storage.
- **Storage**: Replace SQLite with Postgres for multi-replica; or keep SQLite per edge node and aggregate via central API.
- **Reference**: ~51 vCPU, 232 GB RAM, 350 TB object storage for 1,000 cameras (industry reference); scale horizontally by adding nodes and sharding by site/camera.

---

## 3. Implementation Checklist (Done / Planned)

| Item | Status | Notes |
|------|--------|--------|
| API v1 endpoints | Done | `/api/v1/analytics/aggregates`, `/api/v1/search`; legacy routes unchanged for compatibility. |
| Health: liveness + readiness | Done | `/health`, `/health/ready` (DB check). |
| site_id on events + list_events filter | Done | Schema + create_event/list_events; camera_id on ai_data. |
| Heatmap / aggregate analytics API | Done | Aggregates by date/hour/event/camera_id; optional site_id filter. |
| Natural language / search API | Done | Keyword search over events and ai_data; extension point for LLM/embeddings. |
| Optional Redis for WS broadcast | Done | Env REDIS_URL; publish on event create/ack; subscriber thread. |
| Frontend: search + analytics | Done | Events search bar; Analytics view with aggregates table. |
| Document Docker/K8s path | Done | This doc + README. |
| Resource-level RBAC | Done | user_site_roles table; GET/PUT /api/v1/users/<id>/sites; events, get_data, aggregates, search, export_data scoped by allowed sites; /me returns allowed_site_ids. |
| Password expiry and history | Done | PASSWORD_EXPIRY_DAYS, PASSWORD_HISTORY_COUNT; /me, POST /change_password; login rejects expired; Settings change-password form. |
| Optional MP4 recording export | Done | GET /recordings/<name>/export?format=mp4 when ffmpeg available; Export view AVI/MP4 buttons. |
| System Status & Network Health | Done | GET /api/v1/system_status (DB, uptime, per-camera status); Dashboard section; GET /api/v1/cameras/detect for autodetect. |
| Camera autodetection | Done | Backend probes indices 0–9 and /dev/video*; Dashboard “Detect cameras” button. |
| Frontend UI audit | Done | docs/FRONTEND_UI_AUDIT.md: score 78/100, improvements list, real data only, no dummy. |
| Enterprise data display | Done | Events: severity filters/summary; Timeline: expandable metadata; Analytics: date range + summary cards; Dashboard: event activity by severity; empty states throughout. |

---

## 4. AI/ML Extension Points

- **Search**: `POST /api/v1/search` with `{"q": "..."}`. Today: match events/ai_data by keyword in event_type, object, metadata. Later: embed query, vector search, or call external NL service.
- **Summarization**: Webhook or internal job: on “export clip” or “review period”, POST clip metadata to `SUMMARIZATION_WEBHOOK_URL`; response can be stored and shown in UI.
- **Analytics pipeline**: Current `analyze_frame()` is one loop. Refactor to a list of “analytics steps” (motion, YOLO, LPR, loiter, line-cross, custom) so new steps (e.g. cloud inference) can be added without changing core loop.
- **Heatmap**: Store or aggregate “person in zone” counts per (camera_id, zone_index, time_bucket). Expose `GET /api/v1/analytics/heatmap?site_id=&from=&to=&bucket=1h`.

---

## 5. Maximum Value Summary

To match best-in-class and enable future scale:

1. **Adopt API versioning and robust health** for zero-downtime and load balancer integration.
2. **Add analytics and search APIs** (heatmap, NL/search stub) to support dashboards and future LLM/semantic search.
3. **Make events and data site-aware** and optional Redis for multi-instance event push.
4. **Keep compliance track** (GOVERNMENT_STANDARDS_AUDIT.md) and security hardening in parallel.
5. **Design for edge + cloud**: keep edge analytics on this node; add extension points for cloud NL, summarization, and optional multi-node deployment (Docker/K8s).

This roadmap aligns with enterprise VMS expectations (Milestone/Genetec scale and feature references) and next-gen AI (NVIDIA Metropolis, LLM-based search/summarization) while preserving a single-node, low-friction deployment today.
