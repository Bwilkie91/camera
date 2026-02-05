# Vigil Upgrade — 2026-era detection + ReID + intent

Drop-in upgrade path from YOLOv8n to **YOLO11/YOLO26** with **ByteTrack**, **ReID persistence**, and **loitering/intent** prediction. All local/edge; Mac MPS supported.

## Quick start

```bash
# From project root
pip install -r vigil_upgrade/requirements.txt
python -m vigil_upgrade.main --camera 0
python -m vigil_upgrade.main --video path/to/recording.mp4 --max-frames 500
python -m vigil_upgrade.main --benchmark path/to/video.mp4
```

## Modules

| Module | Role |
|--------|-----|
| **models.py** | Load YOLO (v8/v10/v11/v12/v26), MPS/ONNX; fallback order |
| **tracker_reid.py** | ByteTrack/BoT-SORT + ReID embeddings → match to DB (cosine > 0.85) |
| **db_storage.py** | SQLite: detection_events, tracks, persons, embeddings |
| **predictor.py** | Rules (dwell + night + unknown) + Isolation Forest; motion features |
| **alerts.py** | Console + optional proactive script/webhook/voice |
| **main.py** | Pipeline: source → track → ReID → DB; benchmark mode |

## Config

Edit `config.yaml`: `model.name` (auto | yolov8n.pt | yolo11n.pt | yolo26n.pt), camera source, ReID threshold, predictor/alerts.

## Benchmark & migration

See **docs/UPGRADE_BENCHMARK_AND_MIGRATION.md** for FPS/accuracy testing, ONNX export, and migration steps.
