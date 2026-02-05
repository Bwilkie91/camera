# Research: Collection Optimization

Research-backed recommendations for optimizing the Vigil data collection pipeline (analyze_frame, ai_data batching, events, audio/WiFi/thermal, notable screenshots). Complements **OPTIMIZATION_AUDIT.md** with literature and concrete tuning options.

---

## 1. Frame sampling and analysis interval

### Research

- **Accuracy vs latency**: Higher frame rate improves detection accuracy but increases CPU/GPU and I/O; lower rate reduces load but can miss short-lived events (CCNC 2022, Aalto).
- **Adaptive sampling**: Systems like **JCAB** and **OneAdapt** treat frame sampling as a continuous variable and adapt it to bandwidth, queue depth, and accuracy targets. Lyapunov-style optimization can maintain latency bounds while reducing resource use (15–59% in some studies).
- **Load shedding**: Dropping frames that have no objects of interest preserves latency with minimal accuracy loss when the scene is static.
- **Practical guidance**: For analytics (not live tracking), 1–2 analyses per minute is often enough for occupancy and event logging; 6–12/min improves event capture at higher cost.

### Current behavior

- **Fixed 10s interval**: `time.sleep(10)` after each analysis when recording. One YOLO + optional emotion/pose/LPR/WiFi/audio/thermal per cycle.
- **No adaptive interval**: Same rate whether scene is empty or busy.

### Recommendations

| Tuning | Effect | Implementation |
|--------|--------|-----------------|
| **Configurable interval** | Let ops choose 5s / 10s / 15s / 30s per site. | Env `ANALYZE_INTERVAL_SECONDS` (default 10); clamp 5–60. |
| **Event-driven shortening** | When `event != 'None'` or high crowd/threat, optionally run next analysis sooner (e.g. 5s once). | Optional: next_sleep = 5 if event else ANALYZE_INTERVAL_SECONDS. |
| **Skip analysis when idle** | If no motion and no recent events, consider 20–30s sleep to save CPU (optional). | Optional: motion + loiter/line_cross check; lengthen sleep when “idle”. |

**Suggested default**: Keep 10s; add `ANALYZE_INTERVAL_SECONDS=10` (or 15 for low-power edge) and document in README.

---

## 2. Database write batching

### Research

- **Batch commits vs per-row**: SQLite bulk-insert throughput can vary from tens to tens of thousands of inserts per second depending on commit frequency. One commit per N rows is far faster than one per row (Stack Overflow, SQLite docs).
- **Transaction size**: Single big transaction is fastest for pure bulk load, but batching (e.g. 50–500 rows) gives a good trade-off between visibility delay and commit overhead.
- **WAL**: `PRAGMA journal_mode=WAL` is already used; good for concurrent read/write during batch writes.

### Current behavior

- **ai_data**: Up to `AI_DATA_BATCH_SIZE=3` rows buffered, then one transaction and commit. Events are committed immediately so alerts stay timely.
- **Notable screenshots**: One INSERT + commit per capture (low volume; acceptable).

### Recommendations

| Tuning | Effect | Implementation |
|--------|--------|-----------------|
| **Larger ai_data batch** | Fewer commits per hour; slightly longer delay before rows appear in lists/export. | Env `AI_DATA_BATCH_SIZE` (default 10, max 50). Current 3 → 10 gives ~100s max delay at 10s interval. |
| **Timeout flush** | Avoid holding rows in memory too long when traffic is low. | If oldest row in batch is older than e.g. 120s, commit batch even if not full. |
| **executemany** | Slightly faster than N single executes in a loop. | Use `cursor.executemany(insert_sql, list_of_tuples)` for the batch. |

**Suggested default**: `AI_DATA_BATCH_SIZE=10`, optional 120s timeout flush; consider `executemany` in `analyze_frame` when flushing.

---

## 3. Inference and data-gathering cost

### Research

- **Resolution**: YOLO at 640px (or 416) is standard; full 1280×720 increases cost with diminishing accuracy gain (OPTIMIZATION_AUDIT, Ultralytics).
- **Cascaded / conditional processing**: Run heavy pipelines (DeepFace, full extended attributes) only when needed (e.g. person present, or every N-th cycle) to save CPU.
- **Edge bandwidth**: Frame partitioning and quantization reduce data volume when sending frames off-device; for local-only collection, the main lever is how often and at what resolution we run models.

### Current behavior

- YOLO: `imgsz=_yolo_imgsz` (default 640); one predict per analysis.
- Emotion: DeepFace or EmotiEffLib on full frame (or person crop when available).
- Extended attributes: One DeepFace call (age/gender/optional race) when `ENABLE_EXTENDED_ATTRIBUTES=1` and person bbox present.
- Audio: Queue-based; non-blocking.
- WiFi: Background worker; non-blocking.
- Thermal: Stub or sensor read; low cost.

### Recommendations

| Tuning | Effect | Implementation |
|--------|--------|-----------------|
| **Emotion every N cycles** | Cut emotion cost by 2–4×. | e.g. run emotion only when `(cycle_index % 2 == 0)` or when person detected; env `EMOTION_EVERY_N=1` (every) or 2. |
| **Extended attributes every N** | DeepFace age/gender is expensive. | Run extended only when person and `(cycle_index % 3 == 0)` or env `EXTENDED_EVERY_N=1`. |
| **YOLO confidence filter** | Fewer weak detections → smaller crowds, less noise. | Pass `conf=0.25` (or env `YOLO_CONF`) into `predict()`; store max confidence in ai_data if desired. |

**Suggested default**: Keep current defaults; add envs `EMOTION_EVERY_N`, `EXTENDED_EVERY_N`, `YOLO_CONF` for tuning without code change.

---

## 4. Collection completeness vs cost

### Research

- **Multi-stream**: Edge systems (e.g. BiSwift) show that per-stream tuning plus global resource control improves throughput and accuracy; for a single stream, the main trade-off is which sensors to run each cycle.
- **Guaranteed vs best-effort**: Events and alerts need low latency; analytics rows can be batched and slightly delayed. Audio/WiFi can be sampled asynchronously and attached to the “nearest” frame by timestamp.

### Current behavior

- Every analysis cycle: one frame read, YOLO, motion/loiter/line_cross, emotion, scene, LPR on vehicles, audio_event (last from queue), wifi (last from worker), thermal, extended attributes (when enabled), integrity hash, optional notable screenshot, then ai_data batch append and event insert if applicable.
- All columns (base + audio + extended) are filled when available; missing values are null/empty.

### Recommendations

| Tuning | Effect | Implementation |
|--------|--------|-----------------|
| **Ensure batch flush on stop** | On recording stop, flush remaining ai_data batch so no rows are lost. | On `is_recording = False` (or shutdown), commit `_ai_data_batch` if non-empty. |
| **Audio/WiFi staleness** | If workers are slow, “last” value may be old. | Optional: only attach audio/WiFi to ai_data if timestamp is within last 15–30s; otherwise leave as None to avoid misleading. |
| **Notable screenshot cooldown** | Already per-reason cooldown; avoids disk and DB spam. | Keep; document `NOTABLE_COOLDOWN_SECONDS` and `NOTABLE_*_THRESHOLD` in README. |

**Suggested default**: Add explicit flush of `_ai_data_batch` when recording stops; document collection semantics in COLLECTION_OPTIMIZATION_RESEARCH or OPTIMIZATION_AUDIT.

---

## 5. Summary table

| Area | Current | Research-backed change | Env / config |
|------|---------|------------------------|--------------|
| Analysis interval | 10s fixed | Configurable 5–60s; optional event-driven shorten | `ANALYZE_INTERVAL_SECONDS` |
| ai_data batch size | 3 | 10 (or 20); optional timeout flush | `AI_DATA_BATCH_SIZE`, optional flush timeout |
| DB write | N × execute + 1 commit | Same or `executemany` + 1 commit | — |
| Emotion | Every cycle | Every N-th cycle or when person | `EMOTION_EVERY_N` |
| Extended attributes | Every cycle (if person) | Every N-th when person | `EXTENDED_EVERY_N` |
| YOLO | conf default | Optional conf filter | `YOLO_CONF` |
| Flush on stop | Not explicit | Flush batch when recording stops | Code change |

---

## 6. References

- Edge video analytics: adaptive configuration and bandwidth (JCAB, IEEE TNET 2021).
- OneAdapt: fast configuration adaptation for video analytics (arXiv 2023).
- CCNC 2022: Deep video analytics latency vs accuracy (Aalto).
- AdaFrame: adaptive frame selection for fast video recognition (IEEE).
- SQLite: “Improve INSERT-per-second performance” (Stack Overflow); batch commit vs commit-in-shot.
- BiSwift: bi-level multi-stream edge video analytics (throughput/accuracy).
- OPTIMIZATION_AUDIT.md (this repo): YOLO imgsz, indexes, stream quality, batching.

---

See **OPTIMIZATION_AUDIT.md** for indexes, limits, and stream tuning; **YOLO_INTEGRATION.md** for model and device options.
