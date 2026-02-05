# Identity Markers for AI-Assisted Re-Identification

This document summarizes **research-backed markers** (attributes and signals) that can be **recorded and used with AI** to support finding or re-identifying who someone is across time or cameras. It maps these to the current Vigil schema, recommends recording improvements, and aligns with the project’s civilian-ethics stance (minimization, transparency, lawful basis).

**Scope:** “Identity markers” here mean any stored information that can support **associating a detection with a person** (same visit, same day, or across sessions). This includes soft biometrics, appearance attributes, behavioral cues, and optional embedding-based ReID. It does **not** prescribe facial recognition or other hard biometrics beyond what the system already supports (watchlist, optional).

---

## 1. Research Summary: What Works for Re-Identification

### 1.1 Soft biometrics (survey literature)

**Definition:** Physical, behavioral, or material attributes that are **not uniquely distinctive** on their own but **narrow the set** of candidates and support identification when combined.

| Category | Examples | Use for “who is this?” |
|----------|----------|-------------------------|
| **Demographic** | Age range, perceived gender | Filter by “adult male” etc. |
| **Anthropometric** | Height (estimated), build (slim/medium/heavy) | Same person often has stable height/build across views. |
| **Appearance** | Hair color, hair length, eye color | Stable within session; hair can change day-to-day. |
| **Behavioral** | Gait (walk pattern, posture) | Cloth-invariant; useful when clothing changes. |
| **Material** | Clothing color/type, accessories | Strong within session; weak across days (cloth-changing). |

Surveys report **170+** extractable traits; the most effective for **surveillance re-ID** in practice are: **height, build, hair (color/length), clothing (upper/lower, color), accessories (bag, hat), and gait**.

### 1.2 Attribute-based ReID (Market-1501, Duke, UPAR)

Standard ReID datasets use **structured attribute lists** so models (and operators) can search by description:

- **Market-1501 (27 attributes):** gender, hair length, **sleeve length**, **length of lower-body clothing**, **type of lower-body** (pants/skirt/shorts), **hat**, **backpack**, **bag**, **handbag**, age, **8 upper-body colors**, **9 lower-body colors**.
- **DukeMTMC (23 attributes):** Similar, slightly reduced set.
- **UPAR (40 binary attributes in 12 categories):** Standardized for cross-dataset attribute recognition.

**Takeaway:** The most effective **recordable** markers for “find who this is” are:

1. **Upper body:** color, sleeve length (long/short).
2. **Lower body:** color, length (long/short), type (pants/skirt/shorts).
3. **Accessories:** hat (y/n), backpack (y/n), bag/handbag (y/n).
4. **Demographic:** age range, gender (perceived).
5. **Stable body:** height (estimated), build, hair color/length.
6. **Behavioral:** gait/posture (cloth-invariant; valuable when clothes change).

### 1.3 Cloth-changing and domain shift (2024)

When the **same person** appears in **different clothing**:

- **Weak:** Clothing color alone (unreliable).
- **Strong:** Face (if available), **body shape**, **gait**, **hairstyle** (and to a lesser extent hair color).

So for **cross-day or cross-outfit** re-ID, the most effective markers to **record** are: **gait_notes**, **build**, **estimated_height_cm**, **hair_color** (and ideally hair length), plus **face embedding** (ReID) when enabled and legally justified.

---

## 2. Current Vigil Schema: What We Already Record

The following `ai_data` (and related) fields already support identity-related search and re-association:

| Marker type | Field(s) | Source / notes |
|-------------|----------|-----------------|
| **Identity label** | `individual` | Watchlist match name or “Unidentified”. |
| **Face** | `facial_features`, watchlist embedding | Pose/emotion; optional face embedding for watchlist. |
| **Demographic** | `perceived_gender`, `perceived_age_range` | DeepFace when ENABLE_SENSITIVE_ATTRIBUTES=1. |
| **Anthropometric** | `estimated_height_cm`, `build` | Bbox aspect + heuristics (slim/medium/heavy). |
| **Appearance** | `hair_color`, `clothing_description` | Dominant color in head/body ROI (e.g. “gray top/body”). |
| **Behavioral** | `gait_notes` | From pose (upright, bent_torso, asymmetric, etc.); ENABLE_GAIT_NOTES. |
| **Behavioral** | `pose`, `emotion`, `micro_expression` | Pose/emotion; can support “same person” consistency. |
| **Material** | `clothing_description` | Single string (dominant body color + “top/body”). |
| **ReID embedding** | `proactive/reid`, `vigil_upgrade` embeddings | OSNet/ResNet person-crop embedding (optional; ENABLE_REID). |
| **Context** | `attention_region`, `centroid_nx/ny`, `world_x/world_y` | Where in frame/floor; supports trajectory + “same place, same time”. |
| **Context** | `illumination_band`, `period_of_day_utc` | When/where conditions; filter by context. |
| **Audio** | `audio_transcription`, `audio_sentiment`, speaker attributes | Voice/speech (consent-dependent). |
| **Device** | `device_mac`, `device_oui_vendor`, `device_probe_ssids` | WiFi presence (identity tie-in; use with care). |

**Search:** `POST /api/v1/search` matches on all of the above (including `centroid_nx/ny`, `world_x/world_y`), so operators can query by any combination (e.g. “gray clothing”, “slim build”, “bent_torso gait”) to find relevant rows.

---

## 3. Effective Markers: Prioritized for Recording

To **maximize usefulness for “find who someone is”** while staying within ethical and legal bounds:

### Tier 1 — Already in use (keep and expose in search/export)

- **Height:** `estimated_height_cm`  
- **Build:** `build` (slim/medium/heavy)  
- **Hair:** `hair_color`  
- **Clothing:** `clothing_description` (refine to upper/lower + color if feasible; see below)  
- **Gait/posture:** `gait_notes`  
- **Pose:** `pose`  
- **Demographic (optional):** `perceived_gender`, `perceived_age_range` (only when ENABLE_SENSITIVE_ATTRIBUTES=1)  
- **Identity:** `individual` (watchlist), optional ReID embedding (ENABLE_REID)

### Tier 2 — High value, minimal schema change

- **Upper vs lower clothing:** Split or extend `clothing_description` into **upper color** and **lower color** (and optionally **sleeve length**, **lower length/type**) so queries can be “black top, blue pants”.  
- **Accessories:** Add booleans or short tags: **hat**, **backpack**, **bag** (from object detector or small attribute model).  
- **Hair length:** Add **hair_length** (short/medium/long) if available from existing models.

### Tier 3 — Strong but more invasive

- **Face embedding (watchlist):** Already supported; use only with lawful basis and retention policy (see CIVILIAN_ETHICS_AUDIT_AND_FEATURES.md).  
- **ReID person embedding:** Optional; same ethics as face (default-off, document purpose, no export of embeddings).

---

## 4. Recording Recommendations (Implementation Hooks)

- **Keep and validate:** Ensure `gait_notes`, `build`, `estimated_height_cm`, `hair_color`, `clothing_description` are always written when a person is detected and extended attributes are on; ensure they are in export and search.  
- **Enrich clothing:** Prefer **two fields** (e.g. `clothing_upper`, `clothing_lower`) or a **structured string** (e.g. “upper:gray lower:dark”) so search can target “gray top” or “dark pants” separately.  
- **Accessories:** If YOLO or another model detects “backpack”, “handbag”, “hat”, record as **accessory_hat**, **accessory_backpack**, **accessory_bag** (or a single `accessories` comma-separated list) for attribute-based retrieval.  
- **ReID:** Keep ReID **off by default**; when enabled, document purpose, restrict retention, and do not export raw embeddings (see ethics doc).

---

## 5. Ethics and Compliance

- **Minimization:** Record only the markers needed for the stated purpose (e.g. security, incident review). Use **privacy preset** and **feature flags** (system_status) to run a minimal stack.  
- **Transparency:** “What we collect” (e.g. GET /api/v1/what_we_collect) and signage should mention identity-related data (appearance, gait, optional face/ReID).  
- **Retention:** Apply same retention as other ai_data; shorter retention for embeddings and sensitive attributes where possible.  
- **Search/export:** Attribute and identity markers are searchable and exportable; ensure access control and audit (saved searches, export approval) as in CIVILIAN_ETHICS_AUDIT_AND_FEATURES.md.

---

## 6. References

- Soft biometrics survey (Multimedia Tools and Applications, 2021).  
- Market-1501 Attribute (27 attributes): [GitHub vana77/Market-1501_Attribute](https://github.com/vana77/Market-1501_Attribute).  
- DukeMTMC-attribute (23 attributes): [GitHub vana77/DukeMTMC-attribute](https://github.com/vana77/DukeMTMC-attribute).  
- Masked Attribute Description Embedding (MADE) for cloth-changing ReID (arXiv 2401.05646).  
- Attribute-Guided Pedestrian Retrieval (AGPR), CVPR 2024.  
- CIVILIAN_ETHICS_AUDIT_AND_FEATURES.md (this repo).  
- EXTENDED_ATTRIBUTES.md (this repo).
