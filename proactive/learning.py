"""
On-device continual learning (sketch).

Idea: Use new detections to fine-tune a small head (e.g. LoRA on emotion/gait
classifier) without full retraining. All edge-only; no cloud.

This module is a SKETCH only — no training loop is run by default.
Implement when you have labeled data and a small classifier head.
"""
from __future__ import annotations

# Continual learning approach (2026-style, edge-only):
#
# 1. Freeze the ReID/feature backbone; add a small "head" (e.g. 2-layer MLP)
#    for auxiliary tasks: emotion, gait_class, or intent.
# 2. Collect (embedding, label) from user corrections or high-confidence
#    model outputs. Store in a local buffer (SQLite or file).
# 3. Periodically (e.g. nightly): run a few gradient steps on the head only,
#    using the buffer. Optionally use LoRA-style low-rank updates on the last
#    layer of the backbone for better adaptation.
# 4. No data leaves the device. Retain a small replay buffer (e.g. 10k samples)
#    to avoid catastrophic forgetting; optional reservoir sampling.
#
# Dependencies (optional): torch, peft (for LoRA). Not required for the main
# pipeline; enable only if you implement the training loop.
#
# Example stub for a "head" update (not run automatically):
#
#   def update_emotion_head(model, buffer: list[tuple[ndarray, int]], lr=1e-4):
#       for emb, label in buffer[-1000:]:
#           logits = model.head(torch.from_numpy(emb))
#           loss = F.cross_entropy(logits, torch.tensor([label]))
#           loss.backward()
#       optimizer.step()
#

def placeholder() -> None:
    """Placeholder to make this module importable."""
    pass
