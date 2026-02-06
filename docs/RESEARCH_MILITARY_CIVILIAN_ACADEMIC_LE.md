# Research: Military, Civilian, Academic & Law Enforcement — Additional Standards and Concepts

This document catalogs **additional standards, journals, and concepts** from military, civilian, academic, and law enforcement sources that may have been under-emphasized in existing Vigil documentation. Each section notes the source, the concept, current Vigil alignment (if any), and suggested actions. See **BEST_PATH_FORWARD_HIGHEST_STANDARDS.md** for how these feed into the phased roadmap.

---

## 1. Military / Defense

| Source | Concept | Vigil today | Gap / action |
|--------|---------|-------------|--------------|
| **UFC 4-141-03 (2024)** | DoD Unified Facilities Criteria for C5ISR (Command, Control, Computers, Communications, Cyber, Intelligence, Surveillance, Reconnaissance) facilities; planning and design standards. | Not applicable to software-only VMS; informs facility and network design where Vigil is deployed in DoD sites. | **Doc only:** Reference in RUNBOOKS or INSTALL_AUDIT for “DoD facility deployment” (power, network, physical security). |
| **IARPA Video LINCS (2024)** | Re-identification across diverse video sensors; geo-localization; unified coordinate system; cross-sensor (aerial + ground) object association. | Homography gives world_x/world_y per camera; no cross-camera reID or geo-ref. | **Phase 4:** Cross-camera association and optional geo-tag (see MAPPING_OPTIMIZATION_RESEARCH, IDENTITY_MARKERS_AND_REID). |
| **MISB (NGA/GWG)** | Motion Imagery Standards Board: KLV metadata (e.g. ST 0601 UAS Datalink, ST 0603/0604 time reference and time stamping), ST 0807 KLV dictionary, ST 1204 MIIS. | Export uses UTC in headers and per-row timestamp_utc; no KLV or MISB-format metadata in video. | **Optional:** For DoD/IC interop, document “MISB not supported”; if ever required, add optional KLV/metadata track in export (large effort). |
| **NITF (JITC)** | National Imagery Transmission Format Standard conformance for imagery systems. | Still imagery export (e.g. snapshots) not NITF. | **Doc only:** Note in GOVERNMENT_STANDARDS_AUDIT that NITF applies to still imagery interchange in DoD/IC; not in scope for typical VMS. |
| **GigEVision / event cameras** | Low-latency (<2ms), 10GbE event-based camera interfaces (e.g. Navy SBIR). | Standard IP/RTSP/MJPEG capture; no event-based camera support. | **Doc only:** Document as out-of-scope for current stack; future hardware integration. |

---

## 2. Law Enforcement & Forensic Standards

| Source | Concept | Vigil today | Gap / action |
|--------|---------|-------------|--------------|
| **SWGDE 18-F-002 (2025)** | Best Practices for Digital Evidence **Collection** (v2.0); collection procedures, documentation, chain of custody at acquisition. | Chain of custody on export (SHA-256, operator, system); no explicit “collection” checklist at recording start. | **Action:** Add optional “collection checklist” in UI or export manifest: operator, purpose, time started, camera(s), retention policy (align with RESEARCH_IMPROVEMENTS_ACADEMIC_LE preservation checklist). |
| **SWGDE 23-V-001 (2024)** | Best Practices for Digital Video **Authentication**; integrity, verification, documentation. | Per-row and export SHA-256; verify endpoints; manifest. | Largely aligned. **Optional:** Export certificate/signed manifest (BEST_PATH_FORWARD Phase 3.5). |
| **SWGDE 17-V-001 (2024)** | Technical Overview of Digital Video Files; formats, codecs, metadata. | MP4/H.264 when ffmpeg available; NISTIR-style headers. | **Doc:** Reference in AI_DETECTION_LOGS_STANDARDS; ensure export MIME/filename align with SWGDE/NIST where possible. |
| **OSAC 2024-N-0011** | Forensic Digital Image Management: **Primary** (first recording to media), **Original** (replica), **Working** (for processing), **Backup** (duplicate); **fixity** (checksum verification). | recording_fixity job; integrity_hash on ai_data/events; no explicit Primary/Working/Backup taxonomy in UI. | **Action:** Document in RUNBOOKS or AUDIT that “recorded file = primary; export = working copy; backup = operator responsibility”; fixity job aligns with OSAC fixity. Optional: tag exports as “working image” in manifest. |
| **BWC policies (e.g. NY 2025, Chicago, NOPD)** | Body-worn camera: retention, buffering (e.g. 10+ hours), encryption in storage (Evidence.com-style), unalterable recording. | Retention and encryption (when implemented) apply to all recordings; no BWC-specific mode. | **Doc only:** If Vigil ever used to *ingest* BWC footage, document retention/encryption alignment; no code change for current use case. |
| **NIST FRVT** | Face Recognition Vendor Test: standardized FNMR/FMR, demographic differential reporting, “wild” (surveillance-like) datasets. | DeepFace/EmotiEffLib used; no FRVT-style accuracy reporting or demographic breakdown. | **Action:** Document in ACCURACY_RESEARCH or EXTENDED_ATTRIBUTES that perceived_gender/age are not FRVT-validated; for high-assurance face use, consider reporting demographic differentials if validated face engine is used (Phase 4). |

---

## 3. Civilian / Privacy & Data Protection

| Source | Concept | Vigil today | Gap / action |
|--------|---------|-------------|--------------|
| **GDPR Art 5 / 6 / 9** | Lawful basis (Art 6); minimization; purpose limitation; **biometric/special categories** (Art 9); DPIA when high risk. | Civilian mode, raw demographics when extended on; LEGAL_AND_ETHICS, CIVILIAN_ETHICS_AUDIT. | **Action:** Add “DPIA reminder” or link in Settings/docs when biometric (face/emotion) or LPR is enabled; document lawful basis in “What we collect” (CIVILIAN_ETHICS §2.1). |
| **EDPB (e.g. facial recognition airports 2024)** | Biometric data = special protection; assess impact on fundamental rights; consider **less intrusive alternatives**; centralized vs device-local storage. | ReID/watchlist opt-in; raw demographics when extended on; no “less intrusive alternative” checklist. | **Doc:** In CIVILIAN_ETHICS or LEGAL_AND_ETHICS, add short “deployment checklist”: purpose, necessity, less intrusive options considered, retention. |
| **UK ICO / Gov.uk DPIA for surveillance** | DPIA required for systematic large-scale monitoring of public areas; when adding/moving/upgrading cameras or using biometric. | No built-in DPIA workflow. | **Action:** Config or docs: “DPIA required when…” (cameras added, biometric on, large-scale); link to template or external DPIA guide. |
| **Retention by purpose** | No fixed retention period in GDPR; retention must be **appropriate to documented purpose**. | RETENTION_DAYS env; retention job. | **Aligned** if operator documents purpose. **Action:** Export and UI show “Retention policy: X days” and optional “Purpose: …” (already in preservation checklist). |
| **Video redaction (GDPR Art 15/17, CCPA)** | When sharing with third parties or responding to SAR: redact faces, plates, identifiers of non-subjects. | No in-app redaction. | **Gap:** Redaction is typically done at export or by downstream tool. **Action:** Document in LEGAL_AND_ETHICS: “For SAR or third-party sharing, use redaction tool (e.g. [list]) on exported video”; optional future: link to redaction API or script. |
| **Transparency (notice, signage)** | Individuals should be informed of surveillance where feasible. | Privacy/signage reminder in CIVILIAN_ETHICS; “What we collect” summary. | **Action:** Ensure “What we collect” and signage reminder are visible in Settings or first-run (see CIVILIAN_ETHICS §2.1). |

---

## 4. Academic Research

| Source | Concept | Vigil today | Gap / action |
|--------|---------|-------------|--------------|
| **IEEE: Chain-of-evidence in surveillance (e.g. 9166491)** | Preserving chain-of-evidence in surveillance video for authentication and trust-enabled sharing. | integrity_hash, timestamp_utc, model_version, system_id, export SHA-256. | Largely aligned; RESEARCH_IMPROVEMENTS_ACADEMIC_LE and AI_DETECTION_LOGS_STANDARDS cover this. |
| **IEEE: On-demand forensic video analytics** | Scalable, on-demand analytics for large-scale surveillance. | Batch analysis at ANALYZE_INTERVAL; search/export. | **Optional:** Document “on-demand re-analysis” (e.g. re-run detector on stored clip) as future enhancement. |
| **CVPR: CLAP (2024)** | Privacy-preserving collaborative anomaly detection without centralizing raw video. | Local edge analytics; no federated learning. | **Doc:** If multi-tenant/multi-site: consider federated or local-only anomaly models (RESEARCH_IMPROVEMENTS_ACADEMIC_LE, ENTERPRISE_ROADMAP). |
| **Gender Shades / demographic differentials** | Facial analysis error rates vary by skin tone and gender (e.g. 34.7% vs 0.8%); audits drive improvement. | DeepFace/EmotiEffLib; no demographic accuracy reporting. | **Action:** Document in ACCURACY_RESEARCH or EXTENDED_ATTRIBUTES that perceived_gender/age may exhibit demographic differentials; recommend NIST FRVT or internal testing if used for high-stakes identification. Optional: log confidence or model version per demographic band for internal audit. |
| **Algorithmic accountability (AI Now, ACM, Frontiers)** | Transparency, explainability, record-keeping for contestation and redress; avoid “accountability capture.” | model_version in every row; audit log; pipeline state API. | **Action:** Expose “what the AI used” (model_version, thresholds) in export or system status; document in STANDARDS_RATING. Optional: CADF-style audit (initiator, target, outcome) for SIEM/oversight. |

---

## 5. International & Application Standards

| Source | Concept | Vigil today | Gap / action |
|--------|---------|-------------|--------------|
| **ISO/IEC 62676** | VMS for security applications: Part 1-1 (system requirements), Part 4 (application guidelines 2025), Part 5/5-1 (camera data specs, environmental tests). | Functional alignment (recording, export, metadata); no formal 62676 conformance claim. | **Doc:** In GOVERNMENT_STANDARDS_AUDIT or STANDARDS_RATING, note alignment with 62676-1-1/4 (requirements, application guidelines) where applicable; conformance testing is out of scope. |
| **NISTIR 8161 / ONVIF export** | MP4, H.264, per-frame UTC, operator/equipment metadata. | Headers and manifest; per-frame UTC is Phase 4 in BEST_PATH_FORWARD. | See RESEARCH_IMPROVEMENTS_ACADEMIC_LE; Phase 4.1. |

---

## 6. Summary: High-priority additions to the roadmap

| Priority | Area | Action (add to BEST_PATH_FORWARD or config) | Status |
|----------|------|---------------------------------------------|--------|
| **P1** | **DPIA / lawful basis** | When biometric or LPR enabled: reminder or link to DPIA; “What we collect” and lawful basis in Settings/docs (civilian). | **Done:** GET /api/v1/what_we_collect returns dpia_recommended; LEGAL_AND_ETHICS § DPIA; .env.example DPIA note. |
| **P1** | **Evidence collection checklist** | Optional “collection checklist” at recording start or in export manifest: operator, purpose, cameras, retention (SWGDE 18-F-002, preservation). | **Done:** incident_bundle includes collection_checklist (operator, purpose, cameras, retention_policy_days). |
| **P2** | **OSAC Primary/Working image** | Document in RUNBOOKS: primary = recorded file; export = working; fixity = OSAC-aligned; optional “working image” in manifest. | **Done:** RUNBOOKS § Evidence and export; recording manifest image_type 'primary'; incident_bundle image_type 'working'. |
| **P2** | **Demographic fairness / FRVT** | Document that perceived_gender/age are not FRVT-validated and may show demographic differentials; optional internal audit or FRVT if face used for ID. | **Done:** GET /api/v1/what_we_collect returns face_attributes_note (NISTIR 8429) when extended attributes on. |
| **P2** | **Video redaction** | Document in LEGAL_AND_ETHICS: for SAR/third-party sharing, use external redaction tool on exported video; no in-app redaction. | **Done:** LEGAL_AND_ETHICS § Video redaction (SAR, third-party sharing); BEST_PATH Phase 4.7. |
| **P3** | **Less intrusive alternatives** | In CIVILIAN_ETHICS or LEGAL_AND_ETHICS: short deployment checklist (purpose, necessity, less intrusive options considered). | Doc: CIVILIAN_ETHICS; optional checklist in deployment docs. |
| **P3** | **ISO/IEC 62676** | Note alignment in GOVERNMENT_STANDARDS_AUDIT; no conformance testing. | Doc: GOVERNMENT_STANDARDS_AUDIT. |

---

## 7. References (citations)

- **Military:** UFC 4-141-03 (DoD C5ISR facilities); IARPA Video LINCS BAA 24-04; MISB/NGA GWG; NITF JITC; Navy SBIR N242-092 (GigEVision).
- **LE:** SWGDE 18-F-002 (2025), 23-V-001 (2024), 17-V-001 (2024); OSAC 2024-N-0011; NIST FRVT; NIST Digital Video Exchange; BWC model policies (NY 2025, Chicago S03-14, NOPD).
- **Civilian:** GDPR Art 5/6/9; EDPB Opinion 2024/11 (facial recognition); UK ICO video surveillance guidance; Gov.uk DPIA for surveillance cameras; CNPD Luxembourg; GDPR/CCPA video redaction guidance (ICO, EDPB, commercial).
- **Academic:** IEEE 9166491 (chain-of-evidence); IEEE on-demand forensic video analytics; CVPR 2024 CLAP; Gender Shades (Buolamwini et al.); AI Now algorithmic accountability; ACM/Frontiers transparency and accountability.
- **Standards:** ISO/IEC 62676-1-1, 62676-4 (2025), 62676-5, 62676-5-1 (2024); NISTIR 8161; ONVIF Export File Format.

---

## 8. Cross-reference to existing docs

- **BEST_PATH_FORWARD_HIGHEST_STANDARDS.md** — Phased roadmap; Phase 1–4 now reference this doc for “missed” areas.
- **CIVILIAN_ETHICS_AUDIT_AND_FEATURES.md** — Transparency, presets, retention; add DPIA and redaction references.
- **LEGAL_AND_ETHICS.md** — Add DPIA trigger, lawful basis, redaction; link to this doc.
- **GOVERNMENT_STANDARDS_AUDIT.md** — Add ISO 62676, SWGDE 18-F-002, OSAC image taxonomy.
- **ACCURACY_RESEARCH_AND_IMPROVEMENTS.md** — Add demographic differential / FRVT note for face attributes.
- **AI_DETECTION_LOGS_STANDARDS.md** — Add SWGDE 17-V-001 reference.
