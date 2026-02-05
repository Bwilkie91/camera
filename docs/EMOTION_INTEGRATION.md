# Emotion Recognition Integration

Vigil supports **facial emotion analysis** during recording. The pipeline uses a unified helper that can run on **DeepFace** (TensorFlow) or **EmotiEffLib** (PyTorch/ONNX, TensorFlow-free). If neither is available, emotion is reported as `Neutral`.

---

## Why a TensorFlow alternative?

- **DeepFace** depends on TensorFlow, which is not yet available on all environments (e.g. **Python 3.14**, some ARM setups). On Python 3.14, `pip install deepface` fails because TensorFlow has no wheel for 3.14.
- **EmotiEffLib** (ex-HSEmotion) is a lightweight, research-grade library with PyTorch and ONNX backends, no TensorFlow, and state-of-the-art results on AffectNet. It is the recommended option when TensorFlow cannot be used.

### Python 3.14 and watchlist

- **Emotion:** Set `EMOTION_BACKEND=emotiefflib` and install with `pip install emotiefflib` (or `emotiefflib[torch]`). The app will use EmotiEffLib when DeepFace is not installed.
- **Watchlist (familiar/stranger):** The watchlist feature uses DeepFace for face embeddings (`DeepFace.represent`). On Python 3.14, DeepFace cannot be installed, so watchlist stays disabled until you use Python 3.11 or 3.12 with TensorFlow, or a future PyTorch-based embedding option is added.

---

## Backends

| Backend     | Package        | Install                    | Notes                          |
|------------|----------------|----------------------------|--------------------------------|
| **DeepFace**   | `deepface`     | `pip install deepface`     | Requires TensorFlow; full frame. |
| **EmotiEffLib**| `emotiefflib`  | `pip install emotiefflib`  | PyTorch/ONNX; optional face crop from YOLO person box. |

**Selection:** Set `EMOTION_BACKEND` in the environment (or `.env`):

- `auto` (default): Prefer DeepFace if available, else EmotiEffLib, else no emotion (Neutral).
- `deepface`: Use DeepFace only (fails if not installed).
- `emotiefflib`: Use EmotiEffLib only (fails if not installed).

---

## Configuration

| Env / location | Description |
|----------------|-------------|
| `EMOTION_BACKEND` | `auto`, `deepface`, or `emotiefflib`. |

No env: backend is chosen automatically; emotion is `Neutral` if neither library is installed.

---

## How it’s used in the app

- **`analyze_frame()`** (while recording) calls **`_get_dominant_emotion(frame, results)`** once per analysis cycle.
- With **EmotiEffLib**, the code optionally crops to the first YOLO “person” bounding box (if `results` is provided) for better focus on a face, then runs the recognizer on that crop or the full frame.
- The returned label (e.g. Neutral, Happy, Sad, Angry) is stored in `ai_data.emotion` and in `facial_features`; it is also used in the analytics pipeline like before.

---

## References

- [EmotiEffLib (PyPI)](https://pypi.org/project/emotiefflib/) — Python package and docs link.
- [EmotiEffLib documentation](https://sb-ai-lab.github.io/EmotiEffLib/) — API, models, and tutorials.
- [DeepFace](https://github.com/serengil/deepface) — original TensorFlow-based option.

See **YOLO_INTEGRATION.md** for object detection and **OPTIMIZATION_AUDIT.md** for performance tuning.
