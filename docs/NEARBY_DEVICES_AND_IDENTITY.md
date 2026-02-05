# Nearby Devices: Current Behavior & Tying to Identity

## 1. What We Do Today

- **Passive WiFi sniffing** (no active ping/ARP): when **ENABLE_WIFI_SNIFF=1**, the app uses **Scapy** on a monitor-mode interface (e.g. `wlan0mon`) to capture 802.11 frames for a short window (e.g. 10 packets, 2s timeout).
- We collect **sender MAC addresses** (`addr2`) from any Dot11 packet and store **one** MAC per analysis cycle in **`device_mac`** in `ai_data` (and in event metadata). So we are **logging at most one “nearby” device MAC per frame-analysis cycle**, not a full list.
- **Default: off** (`ENABLE_WIFI_SNIFF=0`). Requires root/capabilities and a monitor-mode interface.
- We do **not** currently:
  - Ping or probe devices (no ICMP/ARP).
  - Resolve MAC to vendor (OUI).
  - Parse probe requests for SSIDs or Information Elements (IEs).
  - Log multiple MACs per cycle in a structured way.
  - Use Bluetooth or other radios.

So: we are **not** “pinging” devices; we are **passively logging one nearby device MAC per cycle** when WiFi sniff is enabled, with no identity or vendor attached yet.

---

## 2. Research: Tying Device MAC to Identity

Ways to go from “nearby device MAC” to something closer to identity (for security/ops use cases). Many have **privacy and legal implications**; use only where allowed.

### 2.1 OUI (vendor) lookup

- **What**: First 3 bytes of MAC = OUI (Organizationally Unique Identifier). Public registries (e.g. IEEE, MACVendors.com, macaddress.io) map OUI → vendor/manufacturer.
- **Use**: Infer device type (e.g. Apple, Samsung, Cisco). Does **not** identify a person; narrows device class.
- **How**: Local OUI file (e.g. from IEEE) or a vendor lookup API (rate limits apply). Can cache.

### 2.2 Probe request SSIDs

- **What**: Devices send **probe requests** (Dot11ProbeReq) containing **previously used SSIDs** in plaintext (Information Element ID 0).
- **Use**: SSID list can be matched to **public WiFi databases** (Wigle, etc.) to infer **past locations** (venues, offices, homes). Combined with time/location, that can support **re-identification** of the same device over time.
- **Caveat**: Many devices now use **randomized MACs** per SSID or per session; probe SSIDs still leak even when MAC is random.

### 2.3 Probe request fingerprinting (IEs)

- **What**: Probe requests carry **Information Elements** (supported rates, capabilities, vendor-specific). **Order and content** of IEs form a **device fingerprint**.
- **Use**: Even with **MAC randomization**, the same device often sends the **same IE fingerprint**. Research shows **re-identification** across sessions (e.g. ~40% accuracy with one burst, much higher with multiple bursts).
- **Implication**: “Identity” here = **same physical device over time**, not necessarily a name; can be used to link “anonymous” randomized MACs to one device.

### 2.4 Predictable / real MAC exposure

- **Connected devices** often use a **stable MAC** on the current network (no randomization while associated).
- **Fake AP / Hotspot 2.0 (802.11u)** and other techniques can induce devices to send frames with **real** or **less random** MACs.
- **Scrambler seeds** and other PHY-level quirks can aid tracking. These are more research-grade.

### 2.5 Summary table

| Method              | What you get              | Identity link                    | Typical use              |
|---------------------|---------------------------|----------------------------------|---------------------------|
| OUI lookup          | Vendor / device type      | Device class, not person         | Analytics, device mix     |
| Probe SSID list     | Past networks              | Location history → re-id         | Link device to places    |
| IE fingerprint      | Stable device signature    | Same device across MAC changes   | Re-id despite randomization |
| Stable MAC (e.g. connected) | Same MAC over time  | Same device/session             | Session tracking          |

---

## 3. What’s Implemented in This Codebase

When **ENABLE_WIFI_SNIFF=1**:

- **Multiple nearby MACs**: The WiFi worker collects up to **N** MACs per sniff window (default N=10; set **NEARBY_DEVICES_MAX_MACS**). They are stored in **`device_mac`** as a comma-separated string.
- **OUI (vendor)**: The **first** MAC in the list is looked up via **macvendors.com** (cached by OUI). The result is stored in **`device_oui_vendor`** (e.g. "Apple, Inc."). Requires outbound HTTPS.
- **Probe request SSIDs**: From **Dot11ProbeReq** frames, we parse **Dot11Elt** (ID 0) and collect SSIDs. Up to 20 unique SSIDs per cycle are stored in **`device_probe_ssids`** as a JSON array. This supports later tie-in to location/identity (e.g. Wigle or similar DBs).
- **Privacy / compliance**: MAC + SSID + vendor data can support re-identification. Restrict collection and retention to what’s legally and ethically allowed (e.g. internal security only, retention limits, access control).

---

## 4. Short Answers

- **Are we currently pinging and logging nearby devices?**  
  We are **not** pinging. We **passively log one nearby device MAC per analysis cycle** when `ENABLE_WIFI_SNIFF=1`, and store it in `device_mac`.

- **How to tie device to identity?**  
  **Identity** in practice: (1) **Vendor** (OUI) → device type; (2) **Probe SSIDs** + external DBs → location history → re-id; (3) **Probe IE fingerprint** → same device across MAC changes; (4) **Stable MAC** when connected → same device/session. Implementation in this repo can add OUI lookup and optional probe SSID/IE logging as above; tying to a **named person** would require additional, policy-bound systems (e.g. association with auth/accounts or physical access logs).
