# Config directory

- **config.json** — Analytics (loiter zones, crossing lines). Schema:
  - `loiter_zones`: array of polygons; each polygon is array of `[x, y]` (normalized 0–1).
  - `loiter_seconds`: seconds in zone before loitering event (e.g. 30).
  - `crossing_lines`: array of lines; each line is `[x1, y1, x2, y2]` (normalized 0–1).
  Override path via `CONFIG_DIR` and a `config.json` in that directory.

- **cameras.yaml** — Optional camera list when `CAMERA_SOURCES=yaml`. Copy from `cameras.example.yaml` and set URLs/indices. See `docs/TECHNOLOGY_RESEARCH_AND_CONFIG.md` and `docs/CONFIG_AND_OPTIMIZATION.md`.

- **homography.json** — Optional per-camera 3×3 homography for world/floor-plane mapping. Keys: camera_id (e.g. `"0"`). Values: 3×3 matrix (image point [nx,ny,1] → world [wx,wy,w]; output normalized 0–1). Copy from `homography.example.json` and replace with your calibrated H. See `docs/MAPPING_OPTIMIZATION_RESEARCH.md`. When set, pipeline writes `world_x`, `world_y` to ai_data.

  **Calibrating (highest data quality):** Use 4+ point correspondences (e.g. floor corners in image → known positions on a floor plan). Tools: OpenCV `cv2.getPerspectiveTransform` or `findHomography`; many tutorials for "bird's eye view" or "floor plane homography." The identity matrix `[[1,0,0],[0,1,0],[0,0,1]]` means world_x/world_y = centroid_nx/centroid_ny (no real-world mapping). For 85+ physical/context score, provide a calibrated H so world_x, world_y represent floor positions.
