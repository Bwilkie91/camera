# Legal and ethical considerations — proactive surveillance

This document is **not legal advice**. Laws vary by jurisdiction. Consult a lawyer before deploying surveillance, especially with recording, biometrics, or automated deterrence.

---

## Privacy and consent

- **Recording**: Many regions require notice (signs) or consent for video/audio recording. Some require two-party consent for audio. Check your local laws (e.g. GDPR in EU, state laws in the US).
- **Biometrics / ReID**: Storing embeddings or “persistent identity” may be treated as biometric data (e.g. BIPA in Illinois, GDPR Art. 9). Consent or a lawful basis may be required.
- **Scope**: Limit collection to what’s necessary (e.g. your own property, not public spaces or neighbours’ property).

---

## Automated deterrence

- **Lights / siren / voice**: Automated warnings (“You are being recorded — leave now”) can escalate situations or be illegal in some contexts. Use only where you have clear authority and have considered liability.
- **Perimeter action (PERIMETER_ACTION_URL / ALERT_GPIO_PIN)**: When line-cross or loitering is detected, the system can POST to a URL (e.g. relay for spotlight/siren) or set a GPIO pin high for a configurable duration. Use only on your own property and ensure devices (lights, sirens) are under your control; consider false positives before enabling.
- **Autonomous action webhook (AUTONOMOUS_ACTION_URL)**: When threat_score exceeds a threshold and the event type is in an allowed list, the system can POST to a URL (e.g. home-automation lock or relay). This is **opt-in** and carries **high liability**: only enable if you own and control the target system, understand false positives, and accept responsibility. Configure threshold and event types; document purpose and disclaimer.
- **False positives**: Rule-based and ML systems can misclassify. Avoid actions that could harm or intimidate innocent people.

---

## Data retention and security

- **Retention**: Use a defined retention period (e.g. config `retention_days`) and delete or anonymise data after that.
- **Storage**: Keep databases and logs on a secure, access-controlled system. Prefer encryption at rest where possible.
- **No cloud by default**: This pipeline is designed to run locally. Do not send video, embeddings, or PII to the cloud without a clear legal basis and safeguards.

---

## Best practices

- **Document purpose**: Define why you run surveillance (security, safety, etc.) and document it.
- **Minimise**: Disable features you don’t need (e.g. ReID, audio, deterrence) if they’re not justified.
- **Transparency**: Where appropriate, inform people that recording and/or analysis is in use (e.g. signs, policies).
- **Audit**: Log access to and export of surveillance data; review periodically.

---

## Summary

Use this system responsibly and in line with applicable law. The authors are not responsible for misuse or non-compliant deployment.
