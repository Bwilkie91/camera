# Model Upgrade: Benchmark & Migration

Upgrade path from YOLOv8n to YOLO11/YOLO26 (or alternatives) with benchmarks and migration steps. All local/edge; Mac M-series supported.

---

## 1. Model comparison (drop-in for real-time Mac surveillance)

| Model        | Best for              | Speed (Mac M1/M2) | Accuracy | Notes                          |
|-------------|------------------------|-------------------|----------|--------------------------------|
| **YOLOv8n** | Current baseline      | ~30–50 FPS        | Good     | What you have now              |
| **YOLO11n** | Production default    | Similar or better | Better   | Ultralytics recommendation     |
| **YOLO26n** | Edge-first (2026)     | Often faster CPU  | Better   | NMS-free, CoreML export        |
| **YOLO12n** | Research              | Heavier           | Higher   | Attention-based; less stable   |
| **YOLO-World** | Open-vocab (zero-shot) | ~20–40 FPS     | Flexible | Custom classes without retrain |
| **RT-DETR** | Transformer accuracy  | Slower            | High     | Higher latency on edge         |

**Recommendation for your use case (real-time indoor/outdoor on Mac):**

- **Primary:** `yolo11n.pt` or `yolo26n.pt` — best balance of accuracy/speed and Mac support.
- **Fallback:** Keep `yolov8n.pt` if newer weights are not available.
- **Zero-shot:** Use YOLO-World only if you need custom classes without fine-tuning.

---

## 2. Install & MPS setup (Mac M-series)

```bash
# PyTorch with MPS (Metal)
pip install torch torchvision

# Ultralytics (includes YOLO11, YOLO26 when released)
pip install ultralytics

# Verify MPS
python -c "import torch; print('MPS:', torch.backends.mps.is_available())"
```

- **CoreML (optional):** For best on-device speed, export to CoreML:
  ```python
  from ultralytics import YOLO
  m = YOLO('yolo11n.pt')
  m.export(format='coreml', imgsz=640)
  ```

---

## 3. How to benchmark (new vs old on your footage)

### FPS on Mac

```bash
# Benchmark current (YOLOv8n) vs upgrade (YOLO11n) on same video
python -m vigil_upgrade.main --benchmark /path/to/recording.avi
```

This runs 200 frames through each model and prints FPS. For more control:

```python
import time
from ultralytics import YOLO
import cv2

cap = cv2.VideoCapture("path/to/video.mp4")
frames = [cap.read()[1] for _ in range(300) if cap.read()[0]]
cap.release()

for name in ["yolov8n.pt", "yolo11n.pt"]:
    model = YOLO(name)
    t0 = time.perf_counter()
    for f in frames:
        model.predict(f, imgsz=640, verbose=False)
    print(f"{name}: {len(frames)/(time.perf_counter()-t0):.1f} FPS")
```

### Accuracy (if you have labels)

- Use Ultralytics `model.val(data="coco.yaml")` on a validation set.
- Or run both models on the same clips and compare detection counts / IoU against your existing logs (e.g. person counts per hour).

### Low-res / outdoor

- Keep `imgsz=640` (or 480) for speed; increase to 1280 only if you need distant small objects.
- YOLO11/YOLO26 generally handle low light and scale better than v8; test on your own footage.

---

## 4. Migration steps

1. **Install new stack**
   ```bash
   pip install -r vigil_upgrade/requirements.txt
   ```

2. **Try upgrade model without changing app**
   - Set `YOLO_MODEL=yolo11n.pt` (or `yolo26n.pt`) and run your existing Flask app.
   - Or use `vigil_upgrade` pipeline: `python -m vigil_upgrade.main --video 0`.

3. **Retrain / fine-tune (optional)**
   - If you have custom classes or domain data:
     ```python
     from ultralytics import YOLO
     model = YOLO("yolo11n.pt")
     model.train(data="your_data.yaml", epochs=50, imgsz=640)
     ```
   - Then use the best checkpoint (e.g. `runs/detect/train/weights/best.pt`) as `model.name` in config.

4. **Export to ONNX for faster inference**
   ```python
   from ultralytics import YOLO
   m = YOLO("yolo11n.pt")
   m.export(format="onnx", imgsz=640, simplify=True)
   # In config.yaml set model.use_onnx: true, model.onnx_path: "yolo11n.onnx"
   ```

5. **Keep logs compatible**
   - Vigil upgrade uses the same semantic fields (timestamp_utc, object, event, scene, threat_score, etc.). Your existing parser and `proactive` pipeline can still consume logs; ensure `model_version` in logs reflects the new model name.

---

## 5. File layout (vigil_upgrade)

```
vigil_upgrade/
  main.py           # Pipeline + benchmark entry
  models.py         # load_yolo(), v8/v11/v26/ONNX
  tracker_reid.py   # ByteTrack + ReID matching
  db_storage.py     # SQLite events/tracks/persons/embeddings
  predictor.py      # Rules + Isolation Forest (+ motion)
  alerts.py         # Console + optional proactive deterrence
  config.yaml       # Model, camera, thresholds
  requirements.txt
```

The upgrade pipeline is modular: you can keep using your current Flask app and only switch the model (env `YOLO_MODEL`), or run the full `vigil_upgrade` stack with ReID and predictor.
