# Device Auto-Detection (Cameras & Microphones)

How Vigil discovers and integrates cameras and microphones on the host device (e.g. laptop, NUC, Pi), and how this compares to common NVR/VMS and conferencing software.

---

## Behaviour in Vigil

### Cameras

- **Startup**: If `CAMERA_SOURCES` is unset or set to `auto`, the app **auto-detects** cameras at startup by probing OpenCV indices `0` through `9`. Every index that opens successfully is added as a source, so built-in and USB webcams on a laptop are integrated without manual config.
- **Manual override**: Set `CAMERA_SOURCES=0,1` or RTSP URLs to fix specific sources and disable auto-discovery.
- **Runtime discovery**: `GET /api/v1/cameras/detect` probes indices and (on Linux) `/dev/video*`, and returns index, path, resolution, and a **human-readable name** when the OS provides it (see below).
- **Naming**: Display names come from the OS when possible (Linux sysfs/udev, macOS via ffmpeg AVFoundation), otherwise fallbacks like "Built-in Camera" / "Camera 0".

### Microphones

- **Listing**: `GET /api/v1/audio/detect` returns all audio **input devices** (microphones) when PyAudio is installed: index, name, default sample rate, and channel count. No automatic binding to a specific device yet; the existing audio pipeline uses the system default when `ENABLE_AUDIO=1`.
- **Unified devices**: `GET /api/v1/devices` returns both cameras (from camera detect) and microphones (from audio detect), plus `audio_enabled` and whether camera sources are in auto mode. This supports a single “devices” or setup screen in the dashboard.

### Summary

| Feature | Cameras | Microphones |
|--------|---------|-------------|
| Auto at startup | Yes when `CAMERA_SOURCES` unset or `auto` | N/A (audio uses default when `ENABLE_AUDIO=1`) |
| Runtime list API | `GET /api/v1/cameras/detect` | `GET /api/v1/audio/detect` |
| Human-readable names | Linux sysfs/udev, macOS ffmpeg AVFoundation | PyAudio device name |
| Unified API | — | `GET /api/v1/devices` (cameras + mics) |

---

## How Competitors Do It

- **Frigate NVR**: Focuses on IP/ONVIF and config-defined sources; discovery is often manual or via config. Local USB can be added by specifying device.
- **Agent DVR (iSpy)**: Supports a wide set of sources (IP, ONVIF, USB, audio) with **automatic device discovery** and no hard limit on device count. Devices are added and named from what the OS/hardware reports.
- **iSpy (desktop/web)**: Add cameras and microphones from network or local sources; config can be saved and shared.
- **Video conferencing (Zoom, Meet, etc.)**: Enumerate cameras and mics via the browser/OS (getUserMedia, device labels). They rely on the OS for names and default device.

Common patterns:

1. **Enumerate then let user pick** – List cameras and mics, show names, user selects which to use.
2. **Sensible default** – Use “default” or first device when nothing is configured.
3. **OS-backed names** – Use platform APIs (DirectShow, AVFoundation, V4L2/udev) for human-readable names instead of raw indices.

Vigil follows (1) and (3) via the detect APIs and startup auto for cameras; (2) via default camera index `0` and default audio when `ENABLE_AUDIO=1`.

---

## Implementation Notes

- **Linux**: Camera names from `/sys/class/video4linux/videoN/name` and udev (`ID_MODEL`, `ID_V4L_PRODUCT`). Microphones from PyAudio (PortAudio).
- **macOS**: Camera names from `ffmpeg -f avfoundation -list_devices` (video section); fallback labels "Built-in Camera" / "External Camera" for indices 0/1. Microphones from PyAudio.
- **Windows**: Camera detection by probing OpenCV indices; device names would require DirectShow/pygrabber (not implemented). Microphones from PyAudio.
- **Optional deps**: Microphone list requires `pyaudio`. Camera naming on macOS is improved if `ffmpeg` is on the PATH; otherwise fallback names are used.

---

## References

- [CAMERA_DETECTION_AND_NAMING.md](./CAMERA_DETECTION_AND_NAMING.md) – Camera detection and display names.
- Frigate: [frigate.video](https://frigate.video/)
- Agent DVR / iSpy: [ispyconnect.com](https://www.ispyconnect.com/)
- OpenCV: no built-in device enumeration; indices are probed and names from OS where available.
- PyAudio: `get_device_count()`, `get_device_info_by_index()`, filter by `maxInputChannels > 0` for inputs.
- macOS AVFoundation: `ffmpeg -f avfoundation -list_devices true -i ""` for video/audio device list.
