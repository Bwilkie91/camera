# Competitor & Standards Update (2025–2026)

This document captures **new understanding of competitor systems** and **evolving standards** to guide Vigil improvements. See **SURVEILLANCE_COMMAND_COMPETITORS_AND_RATING.md** for the full competitor overview and rating.

---

## 1. Competitor AI & Search (2025–2026)

### Rhombus

- **AI Search**: Natural-language search with **sub-second** investigation times; conversational prompts (e.g. “red van in specific area”, “person in blue shirt carrying package”) return curated results in seconds.
- **Multi-camera analysis** with contextual understanding of complex scenarios.
- **ChatGPT integration (beta)**: NL prompts analyzed within ~60 seconds with 24/7 real-time analysis.
- **Faces 2.0**: Next-generation facial recognition.
- **Combined Event Search**: Unified search across multiple data types.
- **Differentiator**: Open integration, Relay for existing cameras; NL search as core.

### Verkada

- **AI-Powered Search**: Freeform text queries for people and vehicles with detailed attributes.
- **In-house indexing**: Pre-processes video for faster real-time retrieval at scale.
- **Unified ecosystem**: Cameras, access, sensors native to one cloud; **AI Unified Timeline** for incident reconstruction.

### Implications for Vigil

| Capability | Vigil today | Improvement path |
|------------|-------------|------------------|
| Keyword + filter search | ✅ `/api/v1/search`, get_data, events | Extend with **NL_SEARCH_WEBHOOK_URL** (LLM/external NL service); document sub-second target for API. |
| Saved searches | ✅ Saved searches API + audit | Optional search-query audit log (NIST AU-9). |
| Multi-camera / timeline | ✅ Events + ai_data + aggregates | Heatmap APIs present; optional “unified timeline” view. |
| Face path | ✅ Optional DeepFace/watchlist | Document FRVT/demographic limits; 224×224 for age/gender. |

---

## 2. Evidence & Chain of Custody (NIST / ONVIF 2025)

- **NISTIR 8161 Rev.1**: CCTV digital video export profile (FBI-driven); MP4, H.264, **UTC timestamps per frame**, equipment/operator metadata, **digital signatures** for chain of custody.
- **ONVIF Export File Format**: Adopted by NIST; **embedded timestamps**, **cryptographic signing at capture** (ONVIF media signing spec 2025) with camera-specific keys; verification through chain of custody.
- **IEC 62676-2-32**: ONVIF export format in international standard; ~34k profile-conformant products globally.

### Vigil alignment

- Per-row **integrity_hash** (SHA-256); **X-Export-SHA256**; **verify API**; NISTIR-style headers (X-Operator, X-System-ID, etc.).
- **Gap**: Per-frame or per-segment UTC in MP4 (NISTIR Level 0); optional **digital signing** of exports (SWGDE/OSAC); document Level 0 compliance roadmap.

---

## 3. Dependency & Security Posture

- **CVE/dependency process**: Run `pip audit` (or `scripts/audit-deps.sh`) in CI; schedule dependency updates (see **SURVEILLANCE_COMMAND_COMPETITORS_AND_RATING.md**).
- **Production server**: Use **gunicorn** (or uvicorn if moving to ASGI) instead of Flask dev server; document in RUNBOOKS.
- **Optional deps**: **pyotp** (MFA), **redis** (multi-instance), **pip-audit** (audit), **structlog** / **python-json-logger** (structured logs for SOC).

---

## 4. Summary: Prioritized Improvements from Competitor + Standards

1. **NL search extension**: Document and support **NL_SEARCH_WEBHOOK_URL**; target &lt;2s API response for search.
2. **Export**: Document NISTIR 8161 Level 0 roadmap; optional per-frame UTC in MP4; consider signed export (SWGDE/OSAC).
3. **Dependencies**: Pin safe upper bounds; add **gunicorn** to optional/production; **pip-audit** in CI; optional **structlog**.
4. **API validation**: Centralized limit/offset/date validation (e.g. `_api_limit`, `_parse_date_yyyymmdd`) across v1 endpoints.
5. **Competitor parity (medium-term)**: HLS/WebRTC for streams; mobile/PWA; heatmap UI (APIs exist).

---

## References

- Rhombus: [AI Search](https://www.rhombus.com/blog/introducing-ai-search/), [Faster, Smarter Investigations](https://www.rhombus.com/blog/ai-features-smarter-faster-investigations/).
- Verkada: [AI-Powered Search](https://verkada.com/blog/ai-powered-search).
- NIST: [NISTIR 8161 Rev.1](https://www.nist.gov/publications/recommendation-closed-circuit-television-cctv-digital-video-export-profile-level-0); [Digital Video Exchange](https://www.nist.gov/programs-projects/digital-video-exchange-standards).
- ONVIF: [NIST recommends ONVIF Export](https://onvif.org/pressrelease/nist-recommends-onvif-video-export-spec-as-new-standard-for-fbi); [Partnering to Protect Global Video Authenticity](https://www.onvif.org/blog/2025/06/18/partnering-to-protect-global-video-authenticity-standards/).
