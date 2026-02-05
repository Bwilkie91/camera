"""
Multimodal: audio event detection (optional).

If a microphone is available, add sound classification (e.g. YamNet-lite or
simple librosa features) for: glass break, aggressive voices, footsteps.
Fuse with vision threat_score for a combined risk signal.

This module is a STUB. Enable via config: audio.enabled = true.
Requires: librosa, and optionally tensorflow/onnxruntime for YamNet.
"""
from __future__ import annotations

# Approach:
# 1. Capture audio chunks (e.g. 1–3 s) in a ring buffer alongside video.
# 2. Extract features: mel spectrogram or precomputed YamNet embeddings.
# 3. Classify with a small local model (e.g. trained on ESC-50 or custom
#    labels: glass_break, aggressive_voice, footsteps, normal).
# 4. Emit audio_event and optional audio_threat_score; fuse with
#    detection_events in the DB (same timestamp window).
# 5. In predictor: if audio_threat_score > 0 and vision threat > 0,
#    escalate (e.g. increase threat_score by 10).
#
# Privacy: process audio locally; do not stream to cloud. Prefer
# on-device models (TFLite, ONNX) for low latency.
#

def placeholder() -> None:
    """Placeholder to make this module importable."""
    pass
