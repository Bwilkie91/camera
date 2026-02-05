# YOLO (Ultralytics) Integration

Vigil uses **Ultralytics** for object detection: person/vehicle classes drive LPR (license plate on vehicle ROI), loitering/line-crossing (person centroids), and crowd counts. The same API supports YOLOv8, v9, v10, and YOLO11 (YOLO26) — choose by model file.

## Dependency

- **Package**: `ultralytics>=8.0.0` (see `requirements.txt`)
- **Optional**: If `ultralytics` is not installed or model load fails, YOLO is disabled and analytics run without object detection (no LPR on vehicles, no person-based loiter/line-cross, crowd count 0).

## Model selection

| Env var | Description | Default |
|--------|-------------|--------|
| `YOLO_MODEL` or `YOLO_WEIGHTS` | Model path or name (e.g. `yolov8n.pt`, `yolo11n.pt`, or path to custom `.pt`/`.yaml`) | `yolov8n.pt` |
| `YOLO_DEVICE` | Device for inference: `0`, `cpu`, etc. | (auto) |
| `YOLO_IMGSZ` | Input size (e.g. 640, 416). Tune for speed vs accuracy. | `640` |
| `YOLO_CONF` | Confidence threshold (0.01–0.95). Detections below this are discarded; higher = fewer false positives, more missed objects. | `0.25` |

Examples:

```bash
# Default: YOLOv8 nano (fast, good for edge)
export YOLO_MODEL=yolov8n.pt

# Larger/faster variants
export YOLO_MODEL=yolov8s.pt   # small
export YOLO_MODEL=yolov8m.pt   # medium

# Newer Ultralytics models (same API)
export YOLO_MODEL=yolo11n.pt   # YOLO11 nano

# Custom trained weights
export YOLO_MODEL=/path/to/custom.pt

# Force CPU
export YOLO_DEVICE=cpu
```

On first use, Ultralytics downloads the requested pretrained weights (e.g. `yolov8n.pt`) automatically.

## How it’s used in the app

- **`analyze_frame()`** (while recording): runs `yolo_model(frame)` (or skips if YOLO is unavailable), then:
  - **Objects**: class names from detections (e.g. person, car).
  - **LPR**: `lpr_on_vehicle_roi(frame, results)` runs OCR only on vehicle-class boxes.
  - **Loitering / line-crossing**: `_get_person_centroids(frame, results)` and `check_loiter_and_line_cross(frame, results)` use person detections and zones/lines from `config.json`.
  - **Crowd count**: number of **person** detections above `YOLO_CONF`.

If YOLO is disabled, `results` is `None`: LPR returns `'N/A'`, person centroids are empty (no loiter/line-cross from YOLO), and crowd count is 0.

## Accuracy tuning

- **YOLO_CONF**: Raising (e.g. 0.35–0.5) reduces false positives; lowering (e.g. 0.2) can improve recall in difficult lighting. See **ACCURACY_RESEARCH_AND_IMPROVEMENTS.md** for full inventory of data points and research-backed improvements (emotion, LPR, motion, loiter/line-cross, audio).
- **YOLO_IMGSZ**: 640 is standard; 416 is faster, 832 can improve small-object detection at higher compute.

## References

- [Ultralytics Python usage](https://docs.ultralytics.com/usage/python/) — load by path/name, device, conf, export.
- [Ultralytics models](https://docs.ultralytics.com/models/) — v8/v9/v10/YOLO11 and naming (e.g. `yolov8n.pt`, `yolo11n.pt`).
- **ACCURACY_RESEARCH_AND_IMPROVEMENTS.md** — every analyzed data point and how to improve accuracy.
