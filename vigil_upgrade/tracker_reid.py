"""
Tracking + Re-Identification: ByteTrack/BoT-SORT + persistent person memory.

- Use Ultralytics model.track() (ByteTrack or BoT-SORT) for frame-to-frame IDs.
- For each person bbox, compute ReID embedding (OSNet/ResNet fallback) and match
  against SQLite-stored embeddings (cosine sim > threshold = same person).
- Update persons table: visit_count, last_seen_utc, typical_hours; flag anomalies
  (e.g. "stranger 8× at night").
"""
from __future__ import annotations

import time
from typing import Any

import numpy as np

# ReID: use proactive.reid if available, else local stub
def _reid_module():
    try:
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from proactive.reid import (
            compute_embedding,
            embedding_to_blob,
            find_best_match,
            get_embedding_dim,
            is_reid_available,
        )
        return compute_embedding, embedding_to_blob, find_best_match, get_embedding_dim, is_reid_available
    except ImportError:
        return None, None, None, lambda: 128, lambda: False


_compute_embedding, _embedding_to_blob, _find_best_match, _get_embedding_dim, _is_reid_available = _reid_module()


def run_track(
    model: Any,
    frame: np.ndarray,
    persist: bool = True,
    tracker_cfg: str = "bytetrack.yaml",
    conf: float = 0.25,
    iou: float = 0.45,
    imgsz: int = 640,
) -> Any:
    """
    Run detection + tracking (ByteTrack default). Returns Ultralytics Results.
    persist=True keeps IDs across frames when object leaves and re-enters (buffer).
    """
    if model is None:
        return None
    try:
        results = model.track(
            frame,
            persist=persist,
            tracker=tracker_cfg,
            conf=conf,
            iou=iou,
            imgsz=imgsz,
            verbose=False,
        )
        return results
    except Exception:
        return model.predict(frame, conf=conf, iou=iou, imgsz=imgsz, verbose=False)


def crop_person(frame: np.ndarray, box: np.ndarray, padding: float = 0.1) -> np.ndarray | None:
    """Extract person crop from frame given xyxy box; add padding. Returns HWC numpy."""
    x1, y1, x2, y2 = map(int, box[:4])
    h, w = frame.shape[:2]
    pw = max(1, int((x2 - x1) * padding))
    ph = max(1, int((y2 - y1) * padding))
    x1 = max(0, x1 - pw)
    y1 = max(0, y1 - ph)
    x2 = min(w, x2 + pw)
    y2 = min(h, y2 + ph)
    if x2 <= x1 or y2 <= y1:
        return None
    return frame[y1:y2, x1:x2].copy()


def compute_reid_embedding(crop: np.ndarray | None) -> np.ndarray | None:
    """ReID vector from person crop; None if ReID unavailable or crop bad."""
    if _compute_embedding is None or crop is None:
        return None
    return _compute_embedding(crop)


def match_person(
    embedding: np.ndarray,
    conn: Any,
    threshold: float = 0.85,
) -> tuple[int | None, float]:
    """
    Match embedding to stored persons. Returns (person_id or None, similarity).
    If no match above threshold, returns (None, best_sim).
    """
    if _find_best_match is None or embedding is None:
        return None, 0.0
    try:
        try:
            from vigil_upgrade.db_storage import get_all_embeddings
        except ImportError:
            from .db_storage import get_all_embeddings
        stored = get_all_embeddings(conn)
        pid, sim = _find_best_match(embedding, stored, threshold=threshold)
        return pid, sim
    except Exception:
        return None, 0.0


def process_frame_reid(
    frame: np.ndarray,
    results: Any,
    conn: Any,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    For each tracked person in results, compute ReID embedding, match to DB,
    and return list of {track_uid, person_id, embedding, bbox, object_name}.
    If ReID disabled or no person boxes, returns [].
    """
    cfg = config or {}
    reid_cfg = cfg.get("reid", {})
    if not reid_cfg.get("enabled", True):
        return []
    threshold = float(reid_cfg.get("similarity_threshold", 0.85))
    person_class_id = 0  # COCO person = 0

    out = []
    if results is None or (hasattr(results, "__len__") and len(results) == 0):
        return out
    if not hasattr(results, "__iter__"):
        results = [results]
    for res in results:
        if res.boxes is None:
            continue
        boxes = res.boxes
        for i in range(len(boxes)):
            cls_id = int(boxes.cls[i]) if hasattr(boxes, "cls") else 0
            if cls_id != person_class_id:
                continue
            box = boxes.xyxy[i].cpu().numpy() if hasattr(boxes.xyxy, "cpu") else boxes.xyxy[i]
            tid = int(boxes.id[i]) if hasattr(boxes, "id") and boxes.id is not None else None
            if tid is None:
                continue
            crop = crop_person(frame, box)
            emb = compute_reid_embedding(crop)
            person_id = None
            sim = 0.0
            if emb is not None:
                person_id, sim = match_person(emb, conn, threshold=threshold)
            out.append({
                "track_uid": tid,
                "person_id": person_id,
                "embedding": emb,
                "bbox": box.tolist(),
                "object_name": "person",
            })
    return out


def is_reid_available() -> bool:
    """True if ReID backend is loaded."""
    return _is_reid_available() if callable(_is_reid_available) else False


def get_embedding_dim() -> int:
    return _get_embedding_dim() if callable(_get_embedding_dim) else 128


def embedding_to_blob(vec: np.ndarray) -> bytes:
    """Serialize for DB."""
    if _embedding_to_blob:
        return _embedding_to_blob(vec)
    return vec.astype(np.float32).tobytes()
