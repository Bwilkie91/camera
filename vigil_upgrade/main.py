#!/usr/bin/env python3
"""
Vigil Upgrade — main pipeline: camera/video → YOLO track → ReID → DB → predictor → alerts.

Usage:
  python -m vigil_upgrade.main
  python -m vigil_upgrade.main --video path/to/video.mp4
  python -m vigil_upgrade.main --benchmark path/to/video.mp4   # compare models
  python -m vigil_upgrade.main --config path/to/config.yaml
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _load_config(path: str | None) -> dict:
    path = path or (Path(__file__).resolve().parent / "config.yaml")
    if not Path(path).is_file():
        return {}
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        return {}


def run_pipeline(
    video_source: int | str = 0,
    config: dict | None = None,
    max_frames: int | None = None,
) -> None:
    """Run detection + tracking + ReID + DB + predictor loop."""
    import numpy as np

    config = config or _load_config(None)
    try:
        from vigil_upgrade.models import load_yolo, get_model_version
        from vigil_upgrade.db_storage import get_connection, init_schema, insert_detection, store_embedding
        from vigil_upgrade.tracker_reid import run_track, process_frame_reid, embedding_to_blob, get_embedding_dim
    except ImportError:
        from .models import load_yolo, get_model_version
        from .db_storage import get_connection, init_schema, insert_detection, store_embedding
        from .tracker_reid import run_track, process_frame_reid, embedding_to_blob, get_embedding_dim

    model = load_yolo(config=config)
    if model is None:
        print("No YOLO model loaded. Install ultralytics and set model.name in config.")
        return
    print(f"Model: {get_model_version(model)}")

    try:
        import cv2
    except ImportError:
        print("OpenCV required for camera/video.")
        return

    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        print(f"Cannot open source: {video_source}")
        return

    tracker_cfg = config.get("tracker", {}).get("config", "bytetrack.yaml")
    imgsz = config.get("model", {}).get("imgsz", 640)
    conf = config.get("model", {}).get("conf", 0.25)
    reid_enabled = config.get("reid", {}).get("enabled", True)
    dim = get_embedding_dim() if reid_enabled else 0

    with get_connection(config=config) as conn:
        init_schema(conn)
        frame_count = 0
        t0 = time.perf_counter()
        while True:
            ok, frame = cap.read()
            if not ok or (max_frames and frame_count >= max_frames):
                break
            results = run_track(model, frame, tracker_cfg=tracker_cfg, imgsz=imgsz, conf=conf)
            reid_out = process_frame_reid(frame, results, conn, config) if reid_enabled else []
            ts_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            for ro in reid_out:
                insert_detection(
                    conn,
                    timestamp_utc=ts_utc,
                    camera_id="0",
                    object_name=ro.get("object_name"),
                    track_uid=ro.get("track_uid"),
                    person_id=ro.get("person_id"),
                    bbox=(ro["bbox"][0], ro["bbox"][1], ro["bbox"][2] - ro["bbox"][0], ro["bbox"][3] - ro["bbox"][1]) if ro.get("bbox") else None,
                    model_version=get_model_version(model),
                )
                emb = ro.get("embedding")
                if emb is not None:
                    blob = embedding_to_blob(emb)
                    store_embedding(conn, blob, dim, person_id=ro.get("person_id"))
            frame_count += 1
            if frame_count % 100 == 0:
                fps = frame_count / (time.perf_counter() - t0)
                print(f"Frames: {frame_count} FPS: {fps:.1f}")
        cap.release()
    print("Pipeline done.")


def run_benchmark(video_path: str, config: dict | None = None) -> None:
    """Compare YOLOv8n vs configured (or YOLO11n) on same video: FPS and optional mAP."""
    import numpy as np
    try:
        import cv2
        from ultralytics import YOLO
    except ImportError:
        print("Need opencv and ultralytics for benchmark.")
        return
    config = config or _load_config(None)
    imgsz = config.get("model", {}).get("imgsz", 640)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Cannot open {video_path}")
        return
    frames = []
    while len(frames) < 200:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    cap.release()
    if not frames:
        print("No frames.")
        return

    models_to_test = ["yolov8n.pt", config.get("model", {}).get("name") or "yolo11n.pt"]
    for name in models_to_test:
        if not name or name == "auto":
            continue
        try:
            m = YOLO(name)
        except Exception:
            continue
        t0 = time.perf_counter()
        for f in frames:
            m.predict(f, imgsz=imgsz, verbose=False)
        elapsed = time.perf_counter() - t0
        fps = len(frames) / elapsed
        print(f"{name}: {fps:.1f} FPS ({len(frames)} frames in {elapsed:.2f}s)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=str, default="", help="Video file or RTSP URL")
    ap.add_argument("--camera", type=int, default=0, help="Camera index")
    ap.add_argument("--config", type=str, default="", help="Path to config.yaml")
    ap.add_argument("--benchmark", type=str, default="", help="Run benchmark on this video path")
    ap.add_argument("--max-frames", type=int, default=None, help="Stop after N frames")
    args = ap.parse_args()

    config = _load_config(args.config)

    if args.benchmark:
        run_benchmark(args.benchmark, config)
        return

    source = args.video or args.camera
    if args.video and Path(args.video).is_file():
        source = args.video
    run_pipeline(video_source=source, config=config, max_frames=args.max_frames)


if __name__ == "__main__":
    main()
