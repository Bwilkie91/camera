# Incident Response Procedures

Short procedures for security and evidence-related incidents. Align with NIST/CJIS expectations for audit tampering, breach, and evidence preservation.

---

## 1. Suspected audit log tampering

1. **Do not modify or delete** the audit log or database; preserve the current state.
2. **Export verifiable evidence**: As an admin, use **GET /audit_log/export** to download the full audit log CSV (includes per-row `integrity_hash` and export SHA-256). Store the file and note the `X-Export-SHA256` response header.
3. **Verify integrity**: Use **GET /audit_log/verify** (admin) to check that stored `integrity_hash` values match recomputed hashes. A non-zero `mismatched` count indicates possible tampering.
4. **Escalate**: Report to your security or compliance lead; preserve exports and verification result for investigation.
5. **Document**: Record the incident, time of detection, and actions taken in your incident log.

---

## 2. Suspected breach or unauthorized access

1. **Contain**: Revoke or rotate credentials (e.g. change `ADMIN_PASSWORD`, `FLASK_SECRET_KEY`); disable affected accounts if user management is extended.
2. **Preserve**: Export audit log (see §1) and any relevant recordings or exports before making destructive changes.
3. **Assess**: Review audit log and application logs for scope of access (who, when, what resources).
4. **Remediate**: Patch vulnerabilities, enforce MFA (`ENABLE_MFA=1`), and reinforce access controls as needed.
5. **Document**: Record timeline, impact, and remediation; retain evidence for legal or regulatory requirements.

---

## 3. Evidence preservation (legal / disclosure)

1. **Identify** the time range, cameras, and events in scope.
2. **Export recordings**: Use **GET /recordings/<name>/export** for each relevant recording; retain the response headers (X-Export-UTC, X-Operator, X-System-ID, X-Export-SHA256) and optionally **GET /recordings/<name>/manifest** for a standalone manifest.
3. **Export audit trail**: Use **GET /audit_log/export** to capture who accessed or exported what and when.
4. **Do not delete** the source recordings or audit log until release is authorized; consider copying exports to a legal-hold location and documenting the chain of custody (operator, time, system ID are in export metadata).
5. **Document**: Record the preservation request, what was exported, and where it is stored.

---

## 4. Operational notes

- **Retention**: Configure `RETENTION_DAYS` and `AUDIT_RETENTION_DAYS` per policy; ensure audit log retention is long enough for incident review.
- **Backups**: Back up `surveillance.db` and critical config (e.g. `config.json`) regularly; store backups in a secure, access-controlled location.
- **Vulnerability management**: Keep dependencies (e.g. `requirements.txt`) and the OS updated; run CVE scans when available and remediate high/critical findings.

For full compliance expectations, see **GOVERNMENT_STANDARDS_AUDIT.md** and your organization’s incident response plan.
