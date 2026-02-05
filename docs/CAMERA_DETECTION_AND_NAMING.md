# Camera Detection & Naming

How the system discovers cameras and assigns display names (titles) for the UI.

---

## Detection Techniques

### 1. **Configuration and auto-detection (CAMERA_SOURCES)**

- Env `CAMERA_SOURCES` lists sources used at startup: indices (`0`, `1`) or URLs (`rtsp://host/path`).
- **Auto-detect**: If `CAMERA_SOURCES` is unset or set to `auto`, the app probes OpenCV indices 0–9 at startup and uses every camera that opens (e.g. laptop built-in + USB webcams are integrated automatically).
- Otherwise each listed source is opened with OpenCV `cv2.VideoCapture(index)` or `cv2.VideoCapture(url)`.
- Only successfully opened sources are kept and appear as streams.

### 2. **Runtime autodetect (GET /api/v1/cameras/detect)**

- **Index probe**: Tries OpenCV indices `0`–`9`; if `cap.isOpened()`, the device is reported with resolution.
- **Linux device names**: For each index (and for `/dev/video*` not already opened), the system tries to read a human‑readable name:
  - **Sysfs**: `/sys/class/video4linux/videoN/name` (V4L2 driver name).
  - **Udev**: `udevadm info --query=property --name=/dev/videoN`; uses `ID_MODEL` or `ID_V4L_PRODUCT` when present.
- **Response**: Each detected device includes `index`, `path`, `opened`, `resolution`, and `name` (when available).

### 3. **Display name (titling) for streams and status**

Display names are chosen in this order:

1. **DB label** – If `camera_positions` has a non‑default `label` for that `camera_id`, that label is used.
2. **OS device name** – For index‑based sources (e.g. `0`, `1`):
   - Linux: read `/sys/class/video4linux/videoN/name`, or udev `ID_MODEL` / `ID_V4L_PRODUCT`.
   - Produces names like "Integrated Camera", "USB Camera", or the vendor product name.
3. **URL‑derived** – For RTSP/HTTP(S) URLs, a short label is built from the host (e.g. "RTSP (192.168.1.10)").
4. **Fallback** – `"Camera {id}"` (e.g. "Camera 0").

So cameras are **correctly titled** using hardware/OS names when available, and RTSP host when applicable.

---

## References

- **Linux V4L2**: `/sys/class/video4linux/` (kernel.org); udev properties (e.g. ID_MODEL) for USB devices.
- **OpenCV**: No built‑in device name API; detection is done by probing indices and reading OS metadata.
- **macOS**: Device names from `ffmpeg -f avfoundation -list_devices` (video section); fallback labels "Built-in Camera" / "External Camera" for index 0/1.
- **Cross‑platform**: On Windows, DirectShow device names would require another method (e.g. pygrabber); current implementation focuses on Linux/sysfs/udev and macOS/ffmpeg.
