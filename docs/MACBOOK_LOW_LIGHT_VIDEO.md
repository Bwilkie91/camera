# MacBook Pro, MacBook Air & Laptop Video — Capture and Low-Light Enhancement

How to use the built-in camera on a MacBook Pro, **MacBook Air**, or other laptop with this system, and how to enable **low-light enhancement** and **clarity** tuning for better image quality. MacBook Air built-in cameras benefit from the **macbook_air** preset in dim conditions.

---

## 1. Capturing Video from a MacBook Pro

### How it works

- The app uses **OpenCV** `cv2.VideoCapture`. On **macOS**, when the source is a **device index** (e.g. `0` for the built-in FaceTime HD camera), the backend uses **AVFoundation** (`CAP_AVFOUNDATION`) so the built-in camera is opened correctly.
- **CAMERA_SOURCES**: Set to `0` for the built-in camera, `auto` (or leave unset) to auto-detect all cameras (built-in + external), or `0,1` for multiple devices.
- **Permissions**: macOS will prompt for **Camera** access for the process (Terminal, Python, or your IDE). Grant access in **System Settings → Privacy & Security → Camera** if the camera fails to open.

### Configuration

```bash
# Use built-in MacBook camera only
CAMERA_SOURCES=0

# Auto-detect built-in + any USB cameras
CAMERA_SOURCES=auto
```

- Index `0` is typically the **built-in FaceTime HD Camera**; index `1` is often an external USB webcam.
- If the camera does not open, ensure no other app is holding it, and that your OpenCV build includes AVFoundation (standard for `opencv-python` on macOS).

---

## 2. Low-Light Enhancement and Clarity

For dim environments (e.g. indoor or evening use), the app can apply optional **per-frame** processing before streaming and recording:

| Technique | Purpose |
|-----------|--------|
| **CLAHE** (Contrast Limited Adaptive Histogram Equalization) | Improves contrast in shadows and midtones without blowing out highlights. Applied on the **L (luminance)** channel in LAB space. |
| **Gamma correction** | Brightens darker regions non-linearly for a more natural look. |
| **Clarity (unsharp mask)** | Mild sharpening to improve perceived detail and edge clarity. |

These run in the frame pipeline and are **CPU-based**; they are tuned to be fast enough for real-time streaming on a typical laptop.

### Environment variables

| Variable | Default | Description |
|----------|--------|-------------|
| **ENHANCE_VIDEO** | `0` | Set to `1` to enable both low-light and clarity. |
| **ENHANCE_PRESET** | — | Set to **`macbook_air`** for MacBook Air (and similar) built-in cameras: enables low-light + clarity and uses stronger defaults (gamma 1.35, CLAHE 2.2) for dim conditions. |
| **ENHANCE_LOW_LIGHT** | `0` | Set to `1` to enable CLAHE + gamma only. |
| **ENHANCE_CLARITY** | `0` | Set to `1` to enable sharpening only. |
| **ENHANCE_CLAHE_CLIP** | `2.0` (or `2.2` with macbook_air preset) | CLAHE clip limit (higher = more contrast, more noise risk). |
| **ENHANCE_GAMMA** | `1.2` (or `1.35` with macbook_air preset) | Gamma value (>1 brightens dark areas). |

- If **ENHANCE_VIDEO=1**, both low-light and clarity are enabled regardless of the other two.
- **ENHANCE_PRESET=macbook_air** turns on low-light and clarity and uses higher gamma/CLAHE defaults suited to MacBook Air cameras in low light.
- **ENHANCE_LOW_LIGHT** and **ENHANCE_CLARITY** can be used independently (e.g. clarity only in good light).

### Example

```bash
# MacBook Air (or similar): best low-light defaults for built-in camera
ENHANCE_PRESET=macbook_air

# Full enhancement (low-light + clarity) for laptop in dim room
ENHANCE_VIDEO=1

# Or tune separately
ENHANCE_LOW_LIGHT=1
ENHANCE_CLARITY=1
ENHANCE_CLAHE_CLIP=2.0
ENHANCE_GAMMA=1.2
```

### Tuning tips

- **MacBook Air in low light**: Use **ENHANCE_PRESET=macbook_air** for one-shot tuning; optionally add **ENHANCE_GAMMA=1.4** if still too dark.
- **Very dark**: Increase **ENHANCE_GAMMA** (e.g. `1.3`–`1.5`); avoid going too high or the image can look washed out.
- **Noisy image**: Lower **ENHANCE_CLAHE_CLIP** (e.g. `1.5`) to limit contrast boost and noise amplification.
- **Too soft**: **ENHANCE_CLARITY=1** adds a mild unsharp mask; keep low-light settings moderate so sharpening doesn’t emphasize noise.

---

## 3. Pipeline Order

1. **Capture** (OpenCV, AVFoundation on macOS).
2. **Enhance** (if enabled): CLAHE on L channel → merge LAB → BGR → gamma → clarity (unsharp).
3. **Stream** (MJPEG) and **record** (AVI): both use the enhanced frame when enhancement is on.

So both the live view and recordings reflect the same enhancement when **ENHANCE_VIDEO** (or the individual flags) are set.

---

## 4. References

- **OpenCV**: [CAP_AVFOUNDATION](https://docs.opencv.org/4.x/d4/d15/group__videoio__flags__base.html) for macOS/iOS capture.
- **CLAHE**: OpenCV `cv2.createCLAHE()`; often used with LAB luminance for color video.
- **Low-light pipelines**: CLAHE + gamma + (optional) denoise are standard real-time options; see e.g. [Night Video Enhancement using CLAHE](https://github.com/govindak-umd/Night_Video_enhancement_using_CLAHE), [PyImageSearch CLAHE](https://pyimagesearch.com/2021/02/01/opencv-histogram-equalization-and-adaptive-histogram-equalization-clahe).

---

## 5. Troubleshooting

| Issue | What to check |
|-------|----------------|
| Camera does not open on Mac | Camera permission for Terminal/Python/IDE in System Settings → Privacy & Security → Camera. Close other apps using the camera. |
| Black or frozen stream | Try `CAMERA_SOURCES=0` explicitly; ensure OpenCV is built with AVFoundation (default in opencv-python). |
| Image too noisy after enhancement | Lower **ENHANCE_CLAHE_CLIP** and/or **ENHANCE_GAMMA**. |
| Image too flat or washed out | Lower **ENHANCE_GAMMA**; try **ENHANCE_CLARITY=1** only without low-light. |
