"""
Model upgrade path: YOLOv8n → YOLOv10/v11/v12/YOLO26 + alternatives.

Best drop-in for real-time Mac surveillance (2026):
- **YOLO11n** or **YOLO26n**: Ultralytics-recommended production; YOLO26 is edge-optimized, NMS-free.
- **YOLOv8n**: Current baseline; keep as fallback.
- **YOLO-World**: Open-vocab (zero-shot) if you need custom classes without retraining; slightly heavier.

MPS (Apple Silicon): PyTorch 1.12+ / Ultralytics use MPS when available.
ONNX: Export for faster inference; CoreML for best Mac integration.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Fallback order: try latest first, then older (so we get best available)
MODEL_PRIORITY = (
    "yolo26n.pt",   # Edge-first, NMS-free (Ultralytics 2026)
    "yolo11n.pt",   # Production recommendation
    "yolo12n.pt",   # Attention-centric; may be less stable
    "yolov10n.pt",  # v10 nano
    "yolov8n.pt",   # Your current baseline
)

# Alternative families (open-vocab / transformer) — use explicitly via config
MODEL_ALTERNATIVES = {
    "yolo-world": "yolov8s-worldv2.pt",  # Open-vocab; specify classes at runtime
    "rtdetr": "rtdetr-l.pt",             # RT-DETR; transformer, higher accuracy/latency
}


def _device() -> str:
    """Prefer MPS (Mac) > CUDA > CPU."""
    try:
        import torch
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return "cpu"


def load_yolo(
    model_name: str | None = None,
    config: dict[str, Any] | None = None,
    use_onnx: bool = False,
    imgsz: int = 640,
    device: str | None = None,
) -> Any:
    """
    Load YOLO model for detection/tracking.

    model_name: e.g. "yolov8n.pt", "yolo11n.pt", "yolo26n.pt". If None, uses
                config["model"]["name"] or tries MODEL_PRIORITY in order.
    config: optional; may contain model.name, model.use_onnx, model.imgsz.
    use_onnx: if True, look for exported .onnx next to .pt or in config path.
    Returns: Ultralytics YOLO instance (or None if import failed).
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        return None

    cfg = config or {}
    model_cfg = cfg.get("model", {})
    name = model_name or model_cfg.get("name") or os.environ.get("YOLO_MODEL", "")
    use_onnx = use_onnx or model_cfg.get("use_onnx", False)
    imgsz = model_cfg.get("imgsz", imgsz)
    device = device or _device()

    # Resolve model path: try priority list if name is "auto" or empty
    if not name or name.lower() == "auto":
        for candidate in MODEL_PRIORITY:
            try:
                model = YOLO(candidate)
                model.to(device)
                return model
            except Exception:
                continue
        # Last resort: v8n (usually bundled)
        name = "yolov8n.pt"

    # Optional: use ONNX if path provided or exists
    if use_onnx and name.endswith(".pt"):
        onnx_path = Path(name).with_suffix(".onnx")
        if onnx_path.is_file():
            name = str(onnx_path)
        elif model_cfg.get("onnx_path"):
            name = model_cfg["onnx_path"]

    try:
        model = YOLO(name)
        model.to(device)
        return model
    except Exception:
        # Fallback down the priority list
        for candidate in MODEL_PRIORITY:
            if candidate == name:
                continue
            try:
                model = YOLO(candidate)
                model.to(device)
                return model
            except Exception:
                continue
    return None


def get_model_version(model: Any) -> str:
    """Return a string like 'yolov8n' or 'yolo26n' for logging."""
    if model is None:
        return "none"
    try:
        path = getattr(model, "ckpt_path", None) or ""
        if path:
            return Path(path).stem
    except Exception:
        pass
    return "yolo"


# ---- Install / MPS setup notes (for docs) ----
MPS_SETUP_NOTES = """
Mac M-series (MPS) setup:
1. macOS 12.3+, Xcode CLI: xcode-select --install
2. pip install torch torchvision  # PyTorch 1.12+ includes MPS
3. pip install ultralytics
4. Test: python -c "import torch; print(torch.backends.mps.is_available())"
5. YOLO26 CoreML export (optional): model.export(format='coreml') for best on-device speed.
"""

ONNX_EXPORT_NOTES = """
Export to ONNX for faster inference:
  from ultralytics import YOLO
  m = YOLO('yolo11n.pt')
  m.export(format='onnx', imgsz=640, simplify=True)
  # Then use model_cfg.use_onnx: true and onnx_path: 'yolo11n.onnx'
"""
