# Research-Backed Improvements: Academic & Law Enforcement Sources

This document summarizes **academic research** and **law enforcement / standards** sources, and maps them to **concrete improvements and code implementations** applicable to this codebase. It complements **ENTERPRISE_GOV_STANDARDS_IMPROVEMENTS.md**, **GOVERNMENT_STANDARDS_AUDIT.md**, and **CIVILIAN_ETHICS_AUDIT_AND_FEATURES.md**.

---

## 1. Law Enforcement & Standards

### 1.1 NIST & FBI

| Source | Focus | Implementation relevance |
|--------|--------|---------------------------|
| **NISTIR 8161 Rev.1 (CCTV export)** | MP4 container, H.264, **UTC timestamps per frame**, operator/equipment metadata, **digital signature** for chain of custody. Aligns with ONVIF Export File Format and IEC 62676-2-32. | **Current:** Export headers `X-Export-UTC`, `X-Operator`, `X-System-ID`, `X-Export-SHA256`; manifest endpoint; MP4 when ffmpeg available. **Gap:** No **per-frame UTC in export file** (e.g. timed metadata track); no **cryptographic signature** on export file. |
| **NIST IR 8387 (2022)** | Digital evidence preservation: physical media, digital objects, **law enforcement–generated evidence**; chain of custody; acquisition vs preservation. | **Current:** Legal hold table; retention job excludes held items; incident bundle manifest. **Improve:** Document preservation workflow; optional export bundle that includes “preservation checklist” (hash, timestamp, operator) in a single download. |
| **OSAC 2024-N-0011** | Forensic digital image management: **fixity** (checksum/hash to verify no change); primary vs original vs backup vs working images. | **Current:** Per-row `integrity_hash` on ai_data and events; `GET /api/v1/ai_data/verify`, audit log verify. **Improve:** Optional **periodic fixity re-check** of stored recordings (e.g. SHA-256 on file, store in DB; job to re-compute and alert on mismatch). |
| **NIST Digital Video Exchange** | Standardized export to reduce conversion degradation and support forensics. | Align export MIME and filename with ONVIF/NIST naming where possible; document “evidence-grade export” in UI. |

### 1.2 CJIS Security Policy

| Requirement | Implementation relevance |
|-------------|---------------------------|
| **Access control** | **Current:** RBAC (viewer/operator/admin), user_site_roles, export scoped by site. **Done.** |
| **Data protection lifecycle** | **Current:** Retention, legal hold, audit. **Gap:** Encryption at rest (see GOVERNMENT_STANDARDS_AUDIT). |
| **MFA** | **Current:** Optional TOTP (ENABLE_MFA). **Done.** |

### 1.3 SWGDE (Scientific Working Group on Digital Evidence)

| Document | Focus | Implementation relevance |
|----------|--------|---------------------------|
| **23-V-001** (Digital Video Authentication) | Best practices for **digital video authentication** (March 2024). | **Current:** Integrity hash on export; manifest. **Improve:** Add **export certificate** (e.g. JSON sidecar or signed manifest) with algorithm, timestamp, operator; document “SWGDE-aligned” in export UI. |
| **17-I-001** (Integrity of Imagery) | **Hash integrity**, chain of custody for imagery. | **Current:** SHA-256 on CSV export and recording export. **Improve:** Optional **dual-hash** (e.g. SHA-256 + SHA3-256) for high-assurance deployments; store in manifest. |
| **17-V-002** (Data acquisition from DVRs) | Acquisition from DVRs. | Relevant for ingest from external DVRs; document as future integration. |
| **18-V-001** (Digital forensic video analysis) | Analysis best practices. | Inform runbooks and “evidence handling” doc; no direct code change. |

### 1.4 ONVIF Export File Format

- **Container:** MP4; **codec:** H.264.
- **Per-frame UTC** in export; **timed metadata** (e.g. bounding boxes) possible.
- **Digital signature** on file for chain of custody.
- **Reference:** [ONVIF Export File Format Spec](https://onvif.org/specs/stream/ONVIF-ExportFileFormat-Spec.pdf); open-source player available for verification.

**Code-oriented improvements:**

1. **Frame-level UTC in MP4:** When exporting to MP4 (ffmpeg), write **timed metadata** (e.g. `tmcd` or metadata track) with UTC per frame/gOP so players and forensics tools can display “real-world” time. (Requires ffmpeg metadata mapping from capture timestamps.)
2. **Signed export (optional):** Generate a **signature file** (e.g. PKCS#7 or JSON with signature of file hash + metadata) using a configurable key; document in manifest. Key management: env or HSM (see KEY_MANAGEMENT.md).

---

## 2. Academic Research (2024–2025)

### 2.1 Surveillance video understanding

| Source | Focus | Implementation relevance |
|--------|--------|---------------------------|
| **VALU (CVPR 2024)** | Surveillance **video-and-language** understanding; dataset UCA (23k+ sentences, 110+ hours). Enables semantic queries beyond simple anomaly labels. | **Improve:** Optional **natural-language search** over events/ai_data (e.g. “person in red jacket near entrance”) via embedding of text query + event/attribute embeddings; or integrate a small captioning model for “describe this clip” in incident bundle. |
| **CLAP (CVPR 2024)** | **Privacy-preserving** unsupervised anomaly detection; collaborative learning **without cloud**; works on UCF-Crime, XD-Violence. | **Improve:** If multi-site/multi-tenant: explore **federated or local-only** anomaly models so no raw video leaves the edge; align with “minimal preset” and privacy doc. |
| **Argus** | **Distributed video analytics** across overlapping cameras; object-wise spatio-temporal association; **7.13× fewer object IDs**, **2.19× lower latency** vs per-camera. | **Improve:** With multiple cameras and world_x/world_y (homography), implement **cross-camera association** (same identity across cameras) to reduce redundant detections and improve “one trajectory per person” (see MAPPING_OPTIMIZATION_RESEARCH.md P4). |
| **CUE-Net** | Violence detection with **spatial cropping** + UniformerV2; better for **distant/obscured** subjects. | **Improve:** For “notable behavior” or violence detection, consider **ROI cropping** before classifier (already have person bbox); optional second-stage model. |
| **MadEye** | **Adaptive PTZ** camera orientation to maximize analytics accuracy; **2.9–25.7% accuracy gain** or **2–3.7× cost reduction**. | **Improve:** If PTZ supported: API or config for “optimal orientation” suggestions based on recent heatmaps or event density (research-only unless PTZ hardware integrated). |

### 2.2 Evidence and audit

| Source | Focus | Implementation relevance |
|--------|--------|---------------------------|
| **CADF (Cloud Auditing Data Federation)** | Audit event model: **observer**, **initiator**, **action**, **target**, **outcome**. | **Improve:** Extend audit log schema or export to include **initiator/target/outcome** explicitly (e.g. `action=export_data`, `target=ai_data`, `outcome=success`); optional CADF-JSON export for SIEM integration. |
| **Encrypted trace logs** | Secure auditing with **encrypted** logs in multi-cloud. | **Improve:** Optional **encryption of audit_log** at rest (e.g. per-row or per-table with key from env); or hash-chain so tampering breaks chain. |

---

## 3. Current Codebase Mapping (Summary)

| Area | Already implemented | Gap / next step |
|------|--------------------|------------------|
| **Export metadata** | X-Export-UTC, X-Operator, X-System-ID, X-Export-SHA256, X-Retention-Policy-Days; manifest; incident_bundle | Per-frame UTC in MP4; digital signature on file |
| **Integrity** | integrity_hash on ai_data, events, audit_log; verify endpoints; **recording_fixity** table + fixity job (ENABLE_RECORDING_FIXITY) | Optional dual-hash |
| **Legal hold** | legal_hold table; retention job excludes held; **preservation_checklist** in incident_bundle manifest | — |
| **Audit** | audit_log with action, resource, details; integrity_hash; export/verify | CADF-style fields; optional audit encryption |
| **Video export** | AVI/MP4 (ffmpeg); manifest; NISTIR-style headers | ONVIF-style timed metadata; signed export |
| **Analytics** | Spatial/world heatmap; centroid; homography; search | Cross-camera association (P4); optional NL search |

---

## 4. Recommended Code Implementations (Prioritized)

### P1 — High value, moderate effort

1. **Recording fixity job** — **Implemented**  
   - **What:** Background job (same 6h interval as retention) that, for each recording file, computes SHA-256 and compares to stored value in `recording_fixity` table. On mismatch: structured log `fixity_mismatch`.  
   - **Why:** OSAC/SWGDE fixity; detect bit rot or tampering.  
   - **Code:** Table `recording_fixity (path, sha256, checked_at)`; `_compute_recording_sha256(path)`; `fixity_job()` when `ENABLE_RECORDING_FIXITY=1`; manifest includes `fixity_stored_sha256`, `fixity_checked_at`, `fixity_match`. System status `feature_flags.recording_fixity`.

2. **Export manifest includes preservation checklist** — **Implemented**  
   - **What:** In incident_bundle, each recording in range gets `sha256_verified_at_export` and `export_utc`; manifest includes **preservation_checklist** with description (NIST IR 8387 / SWGDE), export_utc, operator, and **items** (each recording with sha256, verified_at_export_utc; plus ai_data export_url).  
   - **Why:** NIST IR 8387; single place for evidence handlers to verify.

3. **Per-frame or per-segment UTC in MP4 export**  
   - **What:** When exporting to MP4, use ffmpeg to write **timed metadata** (e.g. `metadata` filter or `tmcd`) so each frame or keyframe has UTC. Requires capture timestamps passed to export.  
   - **Why:** NISTIR 8161 / ONVIF; frame-accurate time in one file.  
   - **Code:** In `_export_recording_file` (or equivalent), when building ffmpeg command, add metadata mapping from frame index or timestamp to UTC; document in manifest.

### P2 — Standards alignment, configurable

4. **Optional digital signature on export**  
   - **What:** If configured (e.g. `EXPORT_SIGNING_KEY` path or HSM), produce a **signature file** (e.g. `.export.sig` or JSON with `signature`, `algorithm`, `key_id`, `signed_content_hash`) alongside the exported file. Manifest references it.  
   - **Why:** SWGDE/ONVIF chain of custody.  
   - **Code:** After writing export file, compute hash, sign with private key (PEM or HSM); write sidecar; add to manifest.

5. **CADF-style audit export**  
   - **What:** New endpoint or format: **GET /audit_log/export?format=cadf** returning JSON with observer, initiator, action, target, outcome, timestamp.  
   - **Why:** SIEM and enterprise audit integration.  
   - **Code:** Map `audit_log` rows to CADF event shape; optional.

6. **Dual-hash (SHA-256 + SHA3-256) in manifest**  
   - **What:** When generating manifest, optionally compute and store both hashes.  
   - **Why:** SWGDE 17-I-001; higher assurance.  
   - **Code:** Add `sha3_256` to manifest dict if env `EVIDENCE_DUAL_HASH=1`; use hashlib.sha3_256.

### P3 — Research / longer term

7. **Cross-camera identity association**  
   - **What:** Using world_x/world_y and optional ReID, associate detections across cameras to one “track” or identity per person in the scene.  
   - **Why:** Argus-style efficiency; P4 in MAPPING_OPTIMIZATION_RESEARCH.md.  
   - **Code:** New module or extension of proactive/vigil_upgrade: match by world position + time + optional embedding; store cross_camera_id or merge into existing track table.

8. **Natural-language or attribute query over events**  
   - **What:** Search by sentence (“person in red jacket”) using text embedding + attribute/detection embedding similarity.  
   - **Why:** VALU-style usability.  
   - **Code:** Optional embedding of `event + object + clothing_description + …`; text encoder for query; similarity search in DB or vector store.

9. **Optional ROI/second-stage model for violence or notable behavior**  
   - **What:** For “notable behavior” or violence flag, run a second model on cropped person ROI (e.g. CUE-Net-style or lightweight classifier).  
   - **Why:** Better accuracy on distant/obscured subjects (academic result).  
   - **Code:** In pipeline, after YOLO, optionally call second model on person crop; add score or label to ai_data.

---

## 5. References (URLs and citations)

- **NISTIR 8161 Rev.1:** Recommendation for CCTV Digital Video Export Profile – Level 0 (Revision 1). NIST.  
- **NIST IR 8387:** Digital Evidence Preservation: Considerations for Evidence Handlers (Sept 2022). https://doi.org/10.6028/NIST.IR.8387  
- **OSAC 2024-N-0011:** Standard Guide for Forensic Digital Image Management, Version 1.0 (April 2024).  
- **SWGDE:** Best Practices for Digital Video Authentication (23-V-001); Best Practices for Maintaining the Integrity of Imagery (17-I-001). https://www.swgde.org  
- **ONVIF Export File Format Specification.** https://onvif.org/specs/stream/ONVIF-ExportFileFormat-Spec.pdf  
- **CJIS Security Policy.** https://www.fbi.gov/file-repository/cjis-security-policy  
- **VALU (CVPR 2024):** Towards Surveillance Video-and-Language Understanding (dataset UCA).  
- **CLAP (CVPR 2024):** Collaborative Learning of Anomalies with Privacy.  
- **Argus:** Distributed video analytics across overlapping cameras (object-wise spatio-temporal association).  
- **CADF:** Cloud Auditing Data Federation (event model).  
- **This repo:** ENTERPRISE_GOV_STANDARDS_IMPROVEMENTS.md, GOVERNMENT_STANDARDS_AUDIT.md, MAPPING_OPTIMIZATION_RESEARCH.md, KEY_MANAGEMENT.md.

---

## 6. See also

- **docs/ENTERPRISE_GOV_STANDARDS_IMPROVEMENTS.md** — Implemented standards alignment.  
- **docs/GOVERNMENT_STANDARDS_AUDIT.md** — Gap analysis and ratings.  
- **docs/CIVILIAN_ETHICS_AUDIT_AND_FEATURES.md** — Privacy and civilian use.  
- **docs/AI_DETECTION_LOGS_STANDARDS.md** — AI data and event log integrity.
