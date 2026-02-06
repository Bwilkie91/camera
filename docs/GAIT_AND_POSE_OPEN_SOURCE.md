# Open-Source AI for Body Movement Tracking and Gait Analysis

This document summarizes **open-source pose estimation and gait analysis** tools that can track and analyze body movements (gait, posture, kinematics) and how they relate to this project.

---

## Current Stack (Vigil)

- **Pose**: MediaPipe Pose — used for standing vs person-down (fall) and basic torso angle.
- **Fall detection**: "Fall Detected" is emitted only when pose is Person down **and** the person was seen Standing/Walking within the last **FALL_REQUIRE_RECENT_UPRIGHT_SECONDS** (default 90). This reduces false positives when someone is already lying down (e.g. in bed). Set to `0` to always report fall when pose is Person down. See `.env.example`.
- **Gait**: Stub only — `gait_notes` was fixed to `"normal"`; the app now derives simple posture/symmetry notes from the same pose landmarks when available.

---

## Recommended Open-Source Options

### 1. **MMPose / RTMPose** (best upgrade for pose + kinematics)

- **What**: OpenMMLab pose estimation toolbox; RTMPose is their real-time variant (single- and multi-person).
- **Pros**: Higher accuracy than MediaPipe in benchmarks; real-time (e.g. RTMPose-m ~90+ FPS CPU, 430+ FPS GPU); 2D/3D, whole-body, COCO keypoints; well documented.
- **Use for**: Better joint positions for gait kinematics (hip, knee, ankle), person-down, and future gait metrics.
- **Links**: [MMPose](https://github.com/open-mmlab/mmpose), [RTMPose project](https://github.com/open-mmlab/mmpose/tree/main/projects/rtmpose).
- **Integration**: Optional backend (e.g. `POSE_BACKEND=mmpose` or `rtmpose`) with fallback to MediaPipe; requires PyTorch and OpenMMLab deps (mmcv, mmpose).

### 2. **DeepLabCut (DLC)** (best for custom, high-accuracy gait)

- **What**: Train custom keypoint models on your own videos; DeepLabCut-Live for real-time inference.
- **Pros**: Shown to outperform pre-trained pose models for **gait kinematics** (step length, cadence, etc.) when custom-trained; markerless; used in clinical/gait studies.
- **Cons**: Training pipeline and data labeling; real-time SDK (deeplabcut-live) has Python version constraints (e.g. &lt;3.11).
- **Links**: [DeepLabCut](https://github.com/DeepLabCut/DeepLabCut), [DeepLabCut-Live](https://github.com/DeepLabCut/DeepLabCut-live), [Install](https://deeplabcut.github.io/DeepLabCut/docs/installation.html).
- **Integration**: Use for offline or optional real-time “high-fidelity gait” when you have a trained DLC model; output keypoints can feed the same gait heuristics as MediaPipe/MMPose.

### 3. **OpenPose**

- **What**: Classic 2D multi-person pose (Body_25 keypoints).
- **Pros**: Strong in some gait studies (e.g. knee/hip kinematics); C++ with Python API; pre-trained models.
- **Cons**: Heavier and slower than MediaPipe/RTMPose; less actively developed than MMPose.
- **Integration**: Optional backend if you need maximum compatibility with older gait literature; can map Body_25 to similar joints for stride/symmetry.

### 4. **FastPoseGait / OpenGait** (gait *recognition*, not raw kinematics)

- **What**: **Gait recognition** — identify or re-identify a person by their walking pattern (e.g. silhouette/pose sequences).
- **Pros**: Useful for “who is this walker?” once you have pose or silhouette streams; FastPoseGait is PyTorch, modular, with GCN/Transformer models.
- **Cons**: Different goal than “analyze movement” (step length, limp, cadence); typically need pose or binary masks as input.
- **Links**: [FastPoseGait](https://github.com/BNU-IVC/FastPoseGait), [OpenGait](https://github.com/ShiqiYu/OpenGait).
- **Integration**: Optional module downstream of pose (e.g. run on cropped person + pose keypoints over a short window) for re-ID or behavioral tagging, not for replacing gait_notes.

### 5. **MediaPipe** (current)

- **What**: Lightweight 33-body-landmark pose; single-person focused.
- **Pros**: Already in use; fast; no extra heavy deps; good for fall detection and simple posture.
- **Cons**: Less accurate than MMPose/RTMPose for joint position; not tuned for clinical gait; single-person.
- **Integration**: Remains the default; gait_notes are now derived from these landmarks when available (posture, symmetry).

---

## Gait / Movement Metrics You Can Derive from Pose

From **any** pose backend (MediaPipe, MMPose, OpenPose, DLC) you can compute:

| Metric / feature        | Description (typical approach) |
|-------------------------|---------------------------------|
| **Posture**             | Torso angle, head vs shoulder vs hip (standing / bent / person-down). |
| **Symmetry**            | Left vs right shoulder/hip/knee height or angles; asymmetry can suggest limp or favoring one side. |
| **Stride / step length**| Over time: hip or ankle displacement between “steps” (e.g. peak-to-peak or zero-crossing). |
| **Cadence**             | Steps per minute from temporal peaks of leg angle or vertical motion. |
| **Gait phase**          | Stance vs swing from knee/ankle angles and vertical velocity. |
| **Stability**           | Sway (variation in shoulder/hip center); useful for fall risk or intoxication heuristics (research-only; avoid definitive labels). |

The app’s **gait_notes** currently use a single-frame posture + symmetry heuristic from MediaPipe; adding a **short temporal buffer** (e.g. 1–3 s of pose history) would allow stride/cadence and richer notes (see below).

---

## Integration in This Codebase

### Implemented

- **Pose**: MediaPipe in the main pipeline; runs on largest person crop first (Phase 2.2). `pose` is derived from landmarks: Standing / Sitting / Walking; Person down overrides when torso horizontal. Fall detection unchanged.
- **Gait notes**: `_gait_notes_from_pose()` uses MediaPipe landmarks (when available) to set `gait_notes` from:
  - **Posture**: upright vs bent torso.
  - **Symmetry**: rough left/right shoulder and hip balance (can suggest asymmetry/limping in favorable views).
- **Extended attributes**: `_extract_extended_attributes(..., results_pose=...)` accepts optional pose results so gait_notes are filled from the same frame’s pose without an extra inference.

### Optional future improvements

1. **Temporal gait buffer**  
   Keep a short deque of pose keypoints (e.g. last 30–90 frames at 10 fps). From that:
   - Estimate step events and **cadence** (steps/min).
   - Estimate **stride length** (pixel or normalized) and “normal” vs “short” vs “irregular”.
   - Optionally flag “possible limp” from persistent left/right asymmetry.
   - All of this can still use MediaPipe; switching to MMPose/RTMPose would improve joint accuracy.

2. **Optional MMPose/RTMPose backend**  
   - Env: e.g. `POSE_BACKEND=rtmpose` (or `mmpose`).  
   - Lazy-load MMPose/RTMPose; run on the same crop/frame as current pose step; map COCO (or RTMPose) keypoints to the same format as MediaPipe for `_detect_person_down` and `_gait_notes_from_pose()`.  
   - Keeps one code path for “pose → fall + gait_notes”.

3. **DeepLabCut**  
   - For lab or high-accuracy deployments: train a DLC model on your camera/view; export and run with DeepLabCut-Live or batch; feed keypoints into the same gait logic or a dedicated “high-fidelity gait” path.

4. **Gait recognition (FastPoseGait/OpenGait)**  
   - Add an optional module that consumes pose sequences (or silhouettes) and outputs a gait embedding or ID; use for re-ID or tagging, not for replacing `gait_notes` (which describe movement quality, not identity).

---

## Ethics and Compliance

- **Gait and behavior**: Do not use gait or posture alone to infer protected attributes (e.g. health, intoxication, identity) in a way that affects people’s rights. Prefer descriptive notes (“asymmetric”, “slow cadence”) and use only in line with your compliance docs (e.g. `CIVILIAN_ETHICS_AUDIT_AND_FEATURES.md`).
- **Retention**: Same as other AI data: limit retention, access, and purpose as in your existing policies.

---

## References (summary)

- MMPose: [GitHub](https://github.com/open-mmlab/mmpose), [Docs](https://mmpose.readthedocs.io/).
- RTMPose: real-time pose in MMPose; [OpenReview](https://openreview.net/forum?id=xGKqnb6PeR).
- DeepLabCut and gait: [Nature Scientific Reports (2025)](https://www.nature.com/articles/s41598-025-85591-1); [arXiv 2407.10590](https://arxiv.org/abs/2407.10590).
- Comparison of open-source pose for gait kinematics: [e.g. Flore (UniFi)](https://flore.unifi.it/handle/2158/1405538); [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4013255).
- FastPoseGait: [GitHub](https://github.com/BNU-IVC/FastPoseGait); [arXiv 2309.00794](https://arxiv.org/abs/2309.00794).
