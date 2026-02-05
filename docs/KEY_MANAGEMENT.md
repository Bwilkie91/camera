# Key and secrets management

This document describes how to manage secrets and keys for Vigil in production and high-assurance deployments (NIST, CJIS, ISO 27001).

## Secrets inventory

| Secret / key | Purpose | Env / location | Rotation |
|--------------|---------|----------------|----------|
| **FLASK_SECRET_KEY** | Session signing and CSRF protection | `FLASK_SECRET_KEY` in `.env` | Rotate periodically; invalidates existing sessions. |
| **ADMIN_PASSWORD** | Default admin account (created on first login) | `ADMIN_PASSWORD` in `.env` | Change after first login via Settings; then remove or leave for recovery. |
| **User passwords** | Stored hashes in `users` table | DB | Bcrypt; change via Settings or backend user management. |
| **MFA secrets** | TOTP seeds per user | DB (`users.mfa_secret`) | Per-user; re-setup in Settings if rotated. |
| **ONVIF** | PTZ camera auth | `ONVIF_USER`, `ONVIF_PASS` in `.env` | Rotate when camera credentials change. |
| **Twilio / SMS** | Alert delivery | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` (e.g. in Node `.env`) | Rotate tokens in Twilio console; update env. |
| **Redis** | Multi-instance WebSocket | `REDIS_URL` (may contain password) | Rotate Redis password; update `REDIS_URL`. |

## Storage and handling

- **Never commit** `.env` or any file containing secrets. Use `.env.example` as a template without real values.
- Prefer **environment variables** over config files for secrets so they can be supplied by an orchestrator (Docker, Kubernetes secrets, systemd).
- For **high-assurance** deployments, use a vault (e.g. HashiCorp Vault, cloud KMS) to inject secrets at runtime; avoid long-lived static files on disk.
- **Session cookie**: With `SESSION_COOKIE_SECURE=1` and HTTPS, the session cookie is only sent over TLS. Use a strong `FLASK_SECRET_KEY` (e.g. 32+ random bytes, hex or base64).

## Rotation

- **FLASK_SECRET_KEY**: Generate a new value (e.g. `openssl rand -hex 32`); set in env; restart app. All users must log in again.
- **ADMIN_PASSWORD**: Change via UI (Settings → Change password) or by updating the `users` table hash (use bcrypt); no app restart needed.
- **Database and recordings**: For encryption at rest, use an encrypted volume (LUKS) or application-level encryption with keys from a vault; document key lifecycle per ISO 27001 A.8.24.

## Encryption at rest

Vigil does not implement application-level encryption of the database or recording files. For regulated or high-assurance deployments:

1. **Volume-level encryption (recommended)**  
   Use an encrypted volume (e.g. **LUKS** on Linux, BitLocker on Windows, or an encrypted cloud volume) for the application directory that contains `surveillance.db` and the recordings folder. Keys are managed by the OS or cloud provider; document key lifecycle per ISO 27001 A.8.24.

2. **Application-level (future)**  
   Optional app-level encryption of DB and recordings would require keys from env or a vault; key rotation would need to re-encrypt or support multiple keys. Not implemented in the current codebase; see **docs/SYSTEM_RATING.md** and **docs/APP_REVIEW_AND_RATING.md** for the roadmap.

3. **TLS in transit**  
   Use HTTPS in production (reverse proxy + **ENFORCE_HTTPS=1**); see README § Production HTTPS.

## References

- **README.md** → Configuration, Security & Compliance, Deployment.
- **docs/GOVERNMENT_STANDARDS_AUDIT.md** → NIST/CJIS alignment, audit, MFA, password policy.
