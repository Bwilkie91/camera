# Highest-Grade Mapping Optimizations for Vigil

This document summarizes **research-backed improvements** to optimize spatial mapping, heatmaps, and multi-camera analytics in the Vigil VMS. It covers the current state, high-grade techniques from recent literature, and a prioritized roadmap.

---

## 1. Current State

| Component | What exists | Limitation |
|-----------|-------------|------------|
| **Zones / lines** | `config.json`: `loiter_zones` (polygons), `crossing_lines` (normalized 0–1). Centroid-in-polygon and line-cross in pixel space. | No per-detection (x,y) stored; only zone indices in `zone_presence`. |
| **Camera positions** | `camera_positions` table: (camera_id, site_id, x, y, label) with x,y as 0–1 on site map image. | Used for map markers only; no link to view geometry or FOV. |
| **Map view** | Site map image (map_url) or OSM; camera markers at (x,y) %. | No activity overlay, no heatmap on floor plan. |
| **Heatmap API** | `GET /api/v1/analytics/heatmap`: event counts by date/hour/event_type/camera (time-based, not spatial). | No spatial heatmap (where in frame or on floor). |
| **Zone dwell** | `GET /api/v1/analytics/zone_dwell`: person-seconds per zone index per hour from `zone_presence`. | Good for zone-level occupancy; no fine-grained position. |
| **Attention region** | `attention_region`: left/center/right, top/middle/bottom from bbox center. | Coarse; no numeric (x,y) for heatmap. |

**Now:** We persist **centroid_nx, centroid_ny** (0–1) and optionally **world_x, world_y** when homography is configured (see §4).

---

## 2. High-Grade Improvements (Research)

### 2.1 World / floor-plane mapping (homography)

- **Idea:** Transform image coordinates to a common **world plane** (e.g. floor plan or bird’s-eye view) so positions are comparable across cameras and time.
- **Techniques:**
  - **Homography (H):** 3×3 matrix mapping image (u,v) → plane (x,y). Requires at least 4 point correspondences (e.g. floor corners or known reference points in the scene).
  - **Calibration:** Manual (click floor corners) or automated (e.g. GNN-based homography from bird’s-eye reference; person re-ID as moving keypoints for wide-baseline calibration).
- **References:** IEEE “World Coordinate Virtual Traffic Cameras” (transformation/merging of multiple sources); “Automated Camera Calibration via Homography Estimation with GNNs”; 2D homography to BEV for traffic (image → real-world measurements).
- **Use in Vigil:** Optional per-camera homography (config or DB). Map person centroid (or foot point) to floor (x,y). Enables: single floor-plan heatmap across cameras, path/trajectory in world coords, real-world distances/speeds.

### 2.2 Multi-camera fusion and re-ID

- **Idea:** Same person across cameras → one trajectory in world coordinates.
- **Techniques:**
  - Homography to common plane + trajectory matching (e.g. B-spline trajectories) and/or appearance re-ID.
  - State-aware re-ID: combine geometric consistency (homography) with re-ID correction (CVPRW 2024 AI City; HOTA 67.2%).
  - Wide-baseline calibration using people as keypoints (CVPR 2021).
- **References:** “Multi-Camera Person of Interest Tracking Using Homography and Re-Identification”; “Re-Identification for Multi-Target-Tracking Using Multi-Camera, Homography and Trajectory Matching.”
- **Use in Vigil:** With multiple cameras and homographies, store world (x,y) per detection; optional re-ID for cross-camera identity.

### 2.3 Spatial heatmaps (occupancy / flow)

- **Idea:** Heatmap of “where” people are (or were), not just “when” and “how many.”
- **Techniques:**
  - **Normalized coordinates:** Store (nx, ny) in [0,1] per detection (e.g. centroid or foot in image or floor plane). Aggregate in 2D bins; optional Gaussian KDE for smooth heatmap.
  - **Floor plan:** Map (nx, ny) to floor plan pixels via homography (or 1:1 if already in floor coords). Filter/noise reduction (e.g. distance threshold) before KDE.
  - **Best practice:** Gaussian KDE with bandwidth (e.g. Scott’s rule) for occupancy; color gradient for intensity.
- **References:** “Heatmaps: Improve your spaces” (Density.io); Gaussian KDE occupancy heatmaps (e.g. Nature SData); multi-occupancy with UWB heatmaps + sensors.
- **Use in Vigil:** Persist **primary-person normalized centroid** (centroid_nx, centroid_ny) per row. Then: (1) camera-view heatmap (bin 0–1); (2) after homography, floor-plan heatmap.

### 2.4 Map and UX

- **Idea:** Show activity and heat on the same map operators use.
- **Options:**
  - Overlay heatmap layer on site map image (e.g. canvas or tile layer) from binned (nx,ny) or world (x,y).
  - Per-camera FOV wedge or rectangle on map (from camera_positions + optional FOV params).
  - Time range and camera filters for heatmap; export as image or report.

### 2.5 Data model (minimal for heatmaps)

- **Now:** `zone_presence` = comma-separated zone indices; no (x,y).
- **Add:** `centroid_nx`, `centroid_ny` (REAL, 0–1) for the **primary** person (e.g. first or largest). Enables:
  - Camera-view heatmap API: bin by (centroid_nx, centroid_ny), aggregate count or dwell.
  - Future: homography → world (x,y) stored or computed on read; floor-plan heatmap.

Optional later: `world_x`, `world_y` (after homography); `camera_id` + `homography_id` for multi-camera world view.

---

## 3. Prioritized Roadmap

| Priority | Improvement | Effort | Impact |
|----------|-------------|--------|--------|
| **P0** | Store **centroid_nx, centroid_ny** (0–1) for primary person per detection. | Low | ✅ Implemented. |
| **P1** | **Camera-view heatmap API:** aggregate ai_data by binned (centroid_nx, centroid_ny) over date range; return grid or list for frontend heatmap overlay. | Medium | ✅ Implemented: `GET /api/v1/analytics/spatial_heatmap`; Analytics page widget. |
| **P2** | **Optional homography per camera:** config/DB (4+ point correspondences or 3×3 H). Map centroid to floor (x,y); store or compute world_x, world_y. | High | ✅ Foundation: `config/homography.json` (or `CONFIG_DIR/homography.json`), `world_x`/`world_y` in ai_data when H set. Floor-plan heatmap API next. |
| **P3** | **Map overlay:** heatmap layer on site map (from camera-view bins or world bins). FOV indicators for cameras. | Medium | ✅ Implemented: Map page "Spatial heatmap overlay" (camera-view, last 7 days). |
| **P4** | **Multi-camera world fusion:** homographies + optional re-ID; single world trajectory per identity. | High | Enterprise-grade tracking. |

---

## 4. Implementation Notes

### P0 — Implemented

- **Schema:** `centroid_nx`, `centroid_ny` (REAL) added in `_init_schema`; included in integrity hash and CSV export.
- **Pipeline:** `_get_primary_centroid_normalized(frame, results)` returns (nx, ny) for the largest person bbox; values clamped to [0,1] and rounded to 4 decimals. Written to `data` in `analyze_frame` when present.
- **Search:** `POST /api/v1/search` can match on centroid_nx/centroid_ny (text match).
- **Privacy:** Centroid is one normalized point per frame (primary person only); retention same as other ai_data.

### P2 homography (foundation) — Implemented

- **Config:** Optional `homography.json` in config dir (or `CONFIG_DIR`). Format: `{ "camera_id": [ [h11,h12,h13], [h21,h22,h23], [h31,h32,h33] ] }`. Maps image (nx, ny) to world plane (wx, wy) in [0,1]. Copy from `config/homography.example.json`.
- **Pipeline:** When centroid_nx, centroid_ny are set and homography exists for the current camera_id, `_apply_homography(camera_id, nx, ny)` computes world_x, world_y and they are stored in ai_data.
- **Schema:** `world_x`, `world_y` (REAL); included in hash and export.
- **World heatmap API:** `GET /api/v1/analytics/world_heatmap` (bin by world_x, world_y); Map page floor-plan overlay and Analytics "World heatmap (floor plan)" section.
- **Search:** `POST /api/v1/search` can match on world_x/world_y (text match).

---

## 5. References (summary)

- World coordinate / multi-camera merging: IEEE 9311597.
- Homography calibration with GNNs: OpenAccess CVF / automated calibration.
- BEV / traffic: 2D homography for CCTV→BEV, real-world measurements.
- Multi-camera re-ID + homography: CVPR 2024 AI City; IEEE 10522451; TUM re-ID.
- Wide-baseline calibration from re-ID: CVPR 2021 (Xu et al.).
- Occupancy heatmaps: Gaussian KDE (e.g. Nature SData); Density.io; UWB + sensors (IEEE 10844687).
