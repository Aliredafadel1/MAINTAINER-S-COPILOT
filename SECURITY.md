# SECURITY.md

## Redaction Layer

`app/infra/redaction.py` runs before any log line, trace span, or memory write leaves the service boundary. It is wired into structlog via `_redact_processor` in `app/main.py` — every log event is redacted before serialisation.

### Patterns and Rationale

| Pattern name | Regex | Why |
|---|---|---|
| `api_key` | `(sk\|gh[ps]\|ghs\|ghp\|xox[bpoa])-[A-Za-z0-9\-_]{10,}` | Covers OpenAI (`sk-`), GitHub PATs (`ghp_`, `ghs_`, `gps_`), and Slack tokens (`xoxb-` etc). Issue reporters paste these accidentally in stack traces and config snippets. |
| `jwt` | `eyJ[A-Za-z0-9\-_]+\.[...]+` | JWTs appear in auth error messages. A leaked JWT can be replayed until expiry. |
| `email` | Standard RFC-5322 simplified | Issue reporters include email addresses in bug reports and stack traces. Logged emails create PII exposure. |
| `basic_auth` | `Authorization: Basic [base64]` | HTTP Basic auth headers sometimes appear in curl command examples inside issues. |
| `db_url` | `postgresql://user:password@` | Database URLs with credentials appear in config examples. Credential portion is redacted; the host/DB remain. |
| `aws_key` | `AKIA[0-9A-Z]{16}` | AWS IAM access keys have a fixed prefix. Appear in misconfiguration reports. |

### What is NOT Redacted and Why

- IP addresses: redacting them would remove useful debugging context (e.g. "connection refused at 10.0.0.1:5432")
- Stack trace file paths: useful for debugging; no credentials in paths
- Version strings: needed in logs for diagnosis

### Test Coverage

`tests/test_redaction.py` asserts that:
- A fake OpenAI API key `sk-abcdefghij1234567890` never appears in redacted output
- GitHub tokens, JWTs, emails, Postgres URLs with passwords, and AWS keys are all redacted
- Clean text passes through unchanged (no false positives on normal log content)

CI blocks merge if any redaction test fails (runs in `pytest tests/` job on every push).

---

## Secrets Management

- All secrets resolve from Vault at startup via `app/infra/vault.py`
- `.env` holds only `VAULT_ROOT_TOKEN` and port bindings — no application secrets
- `grep -ri 'sk-' app/` and `grep -ri 'password' app/` return zero matches outside vault-reading code
- The `api` container exits with code 1 if Vault is unreachable — it will not serve traffic without secrets

### Vault Secret Rotation Policy

Secrets live at `secret/data/app` in Vault KV v2. To rotate a secret:

1. Update the value in Vault:
   ```bash
   vault kv patch secret/app NEW_KEY=new_value
   ```
2. Restart the `api` and `modelserver` containers (they load secrets at startup):
   ```bash
   docker compose restart api modelserver
   ```
3. Verify the new secret is loaded:
   ```bash
   docker compose exec api python -c "from app.infra import vault; vault.load_secrets(); print('ok')"
   ```

Vault KV v2 keeps 5 versions by default — rollback is possible via `vault kv rollback`.

**JWT_SECRET rotation note:** Rotating `JWT_SECRET` invalidates all existing user sessions immediately. Users will need to log in again. Plan rotations during low-traffic periods.

**DB_PASSWORD rotation note:** The password must be updated in both Vault (`vault kv patch secret/app DB_PASSWORD=...`) and PostgreSQL (`ALTER USER copilot PASSWORD '...'`) atomically. Use a rolling restart: update Vault → restart api → verify → update PG (brief auth failure window < 30s).

---

## CORS and CSP (Widget)

- CORS `allowed_origins` list is stored per-widget in the `widgets` Postgres table
- The embed route (`GET /widgets/{id}/config`) sets `Content-Security-Policy: frame-ancestors <allowed_origins>` — browser enforces it
- Hardcoded origin allowlists are explicitly forbidden; all changes go through the admin UI and are audit-logged in `audit_log`
- The `public/widget.js` loader is served from the API's `/static/` mount — no CDN, no third-party script hosting

### Origin Allowlist Enforcement

When a widget is embedded on a disallowed origin, the browser blocks the iframe load and logs a CSP violation. The API itself also checks the `Origin` header against the widget's `allowed_origins` list and returns 403 for CORS preflight requests from unlisted origins.

### Audit Logging

All memory writes, widget config changes, and admin actions are written to `audit_log` with `user_id`, `action`, `resource_type`, `resource_id`, and a `details` JSON blob. Audit entries are append-only (no DELETE on the table). Visible in the Streamlit admin UI under "Audit Log".
