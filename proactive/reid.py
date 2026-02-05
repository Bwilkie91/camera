"""
Person Re-Identification: lightweight embeddings for persistent identity.

Uses OSNet (torchreid) when available — runs on Mac M-series via MPS.
Falls back to a simple ResNet-based feature vector or stub when torchreid
is not installed, so the pipeline still runs (matching will be disabled).

Edge-only: no cloud; embeddings stored in local DB. Match by cosine similarity
> threshold (e.g. 0.85) = same person.
"""
from __future__ import annotations

from typing import Any

import numpy as np

# Optional: torchreid for OSNet (Mac MPS compatible)
try:
    import torch
    TORCH_AVAILABLE = True
    MPS_AVAILABLE = torch.backends.mps.is_available() if hasattr(torch.backends, "mps") else False
    DEVICE = torch.device("mps" if MPS_AVAILABLE else "cuda" if torch.cuda.is_available() else "cpu")
except ImportError:
    TORCH_AVAILABLE = False
    MPS_AVAILABLE = False
    DEVICE = None

REID_AVAILABLE = False
_REID_MODEL: Any = None
_REID_DIM = 0


def _load_osnet() -> None:
    """Load OSNet via torchreid if available (Mac MPS compatible)."""
    global REID_AVAILABLE, _REID_MODEL, _REID_DIM
    if not TORCH_AVAILABLE:
        return
    try:
        import torchreid
        # OSNet-x0.25: small, fast, good for edge/Mac
        model = torchreid.models.build_model(
            name="osnet_x0_25",
            num_classes=1,
            pretrained=True,
        )
        model.to(DEVICE)
        model.eval()
        _REID_MODEL = model
        _REID_DIM = 512
        REID_AVAILABLE = True
    except Exception:
        _REID_MODEL = None
        _REID_DIM = 0


def _load_fallback() -> None:
    """Fallback: torchvision ResNet18 backbone for features, or stub dim."""
    global REID_AVAILABLE, _REID_MODEL, _REID_DIM
    if not TORCH_AVAILABLE:
        _REID_DIM = 128
        return
    try:
        import torch
        import torchvision.models as tv
        backbone = tv.resnet18(weights=tv.ResNet18_Weights.IMAGENET1K_V1)
        _REID_MODEL = torch.nn.Sequential(
            *list(backbone.children())[:-1],
            torch.nn.Flatten(),
        )
        _REID_MODEL.to(DEVICE)
        _REID_MODEL.eval()
        _REID_DIM = 512
        REID_AVAILABLE = True
    except Exception:
        _REID_DIM = 128
        _REID_MODEL = None


# Initialize on import
_load_osnet()
if not REID_AVAILABLE:
    _load_fallback()

# Default preprocessing for ReID: resize to 256x128 (person aspect), normalize
REID_INPUT_SIZE = (256, 128)


def _preprocess_crop(crop: np.ndarray) -> "torch.Tensor | None":
    """Convert BGR/RGB numpy crop to tensor for ReID model."""
    if not TORCH_AVAILABLE or _REID_MODEL is None:
        return None
    import torch
    from torchvision import transforms
    if crop is None or crop.size == 0:
        return None
    try:
        # Assume HWC, BGR or RGB
        if len(crop.shape) == 2:
            crop = np.stack([crop] * 3, axis=-1)
        h, w = crop.shape[:2]
        if h < 10 or w < 10:
            return None
        transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize(REID_INPUT_SIZE),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
        x = transform(crop).unsqueeze(0).to(DEVICE)
        return x
    except Exception:
        return None


def compute_embedding(crop: np.ndarray) -> np.ndarray | None:
    """
    Compute ReID embedding from a person crop (numpy array, HWC BGR/RGB).
    Returns vector of shape (dim,) or None if unavailable.
    """
    if _REID_MODEL is None:
        # Stub: return zero vector so callers don't break
        return np.zeros(_REID_DIM or 128, dtype=np.float32)
    x = _preprocess_crop(crop)
    if x is None:
        return None
    with torch.no_grad():
        out = _REID_MODEL(x)
    # OSNet / ResNet may return tuple (logits, features) or single tensor
    if isinstance(out, (list, tuple)):
        out = out[-1]
    vec = out.cpu().numpy().flatten()
    # L2 normalize for cosine similarity
    norm = np.linalg.norm(vec)
    if norm > 1e-6:
        vec = vec / norm
    return vec.astype(np.float32)


def embedding_to_blob(vec: np.ndarray) -> bytes:
    """Serialize embedding to bytes for DB storage."""
    return vec.astype(np.float32).tobytes()


def blob_to_embedding(blob: bytes) -> np.ndarray:
    """Deserialize embedding from DB."""
    return np.frombuffer(blob, dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity [0, 1] if vectors are L2-normalized."""
    if a.size == 0 or b.size == 0:
        return 0.0
    a = a.astype(np.float64).ravel()
    b = b.astype(np.float64).ravel()
    if len(a) != len(b):
        return 0.0
    return float(np.clip(np.dot(a, b), -1.0, 1.0))


def find_best_match(
    embedding: np.ndarray,
    stored: list[tuple[int, int | None, bytes, int]],
    threshold: float = 0.85,
) -> tuple[int | None, float]:
    """
    Find best matching person from stored (id, person_id, blob, dim).
    Returns (person_id or embedding id for new, similarity).
    """
    if not stored or embedding is None or embedding.size == 0:
        return None, 0.0
    best_id: int | None = None
    best_sim = 0.0
    vec = embedding.astype(np.float32)
    if np.linalg.norm(vec) < 1e-6:
        return None, 0.0
    vec = vec / np.linalg.norm(vec)
    for eid, person_id, blob, dim in stored:
        if dim != len(vec):
            continue
        other = np.frombuffer(blob, dtype=np.float32)
        sim = cosine_similarity(vec, other)
        if sim > best_sim and sim >= threshold:
            best_sim = sim
            best_id = person_id if person_id is not None else eid
    return best_id, best_sim


def get_embedding_dim() -> int:
    """Return current ReID embedding dimension."""
    return _REID_DIM or 128


def is_reid_available() -> bool:
    """True if a real ReID model is loaded (not stub)."""
    return REID_AVAILABLE and _REID_MODEL is not None
