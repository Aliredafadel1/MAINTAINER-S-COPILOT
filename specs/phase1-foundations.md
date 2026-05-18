# Phase 1 — Foundations
**Day:** Monday  
**Goal:** Working docker-compose stack with all services wired, secrets in Vault, tracing on from the start, Alembic migrations baseline, and dataset fetched and split.

---

## Deliverables

### 1. Repository Skeleton
- `/app/api/` — HTTP routers only (no DB/Redis/external calls)
- `/app/services/` — business logic, transaction boundaries
- `/app/repositories/` — SQL only, no HTTP errors, no cache
- `/app/domain/` — Pydantic domain models (distinct from SQLAlchemy ORM)
- `/app/infra/` — adapters: Vault, MinIO, Redis, LLM providers, tracing, redaction
- `/prompts/` — all LLM prompt files, version-controlled
- `/migrations/` — Alembic migrations
- `/evals/` — golden sets and eval harness (scaffold only)
- `/demo/host/` — host demo app (scaffold only)
- `/widget/` — React widget source (scaffold only)

### 2. docker-compose Stack
All services defined and healthy-checked:

| Service | Image | Purpose |
|---|---|---|
| `api` | local build | FastAPI app |
| `chatbot` | local build | Streamlit app |
| `widget` | local build | Static React bundle server |
| `modelserver` | local build | Classifier / NER / summarizer inference |
| `host` | nginx | Demo host app |
| `migrate` | local build | Alembic entrypoint, exits 0 |
| `db` | postgres:16 + pgvector | Primary database |
| `redis` | redis:7 | Short-term memory and cache |
| `minio` | minio/minio | Blob storage |
| `vault` | hashicorp/vault (dev mode) | Secrets |

- `migrate` runs `alembic upgrade head` and exits before `api` boots (use `depends_on` with `condition: service_completed_successfully`)
- `api` refuses to boot if Vault is unreachable (startup check in `app/infra/vault.py`)
- `.env.example` with `VAULT_ROOT_TOKEN=` and all port bindings; `.env` is gitignored

### 3. Vault Wiring
- Vault in dev mode, seeded at startup with a script
- Secrets seeded: `LLM_API_KEY`, `JWT_SIGNING_KEY`, `DB_PASSWORD`, `MINIO_SECRET_KEY`, `TRACING_KEY`
- `app/infra/vault.py` reads all secrets at startup; raises `VaultUnavailableError` if unreachable
- `.env` holds only `VAULT_ROOT_TOKEN` and ports — nothing else
- `grep -ri 'sk-' app/` and `grep -ri 'password' app/` return zero matches outside vault-reading code

### 4. Tracing — Wired from Day One
- Pick tracing backend (OpenTelemetry + Jaeger recommended; document choice in `DECISIONS.md`)
- `app/infra/tracing.py` — tracer singleton, span helper
- Every incoming HTTP request gets a trace ID and request ID injected into structured log context
- Trace ID logged alongside every structured log line

### 5. Alembic Baseline Migration
Tables (scaffold, columns to be extended in later phases):
- `users` — id, email, hashed_password, role (`user` | `admin`), created_at
- `conversations` — id, user_id, created_at
- `messages` — id, conversation_id, role, content, created_at
- `memories` — id, user_id, memory_type, content, embedding (vector), created_at
- `widgets` — id, widget_id (public UUID), allowed_origins (jsonb), theme (jsonb), greeting, enabled_tools (jsonb), created_at
- `audit_log` — id, actor_id, action, target, timestamp

### 6. Domain Exception Hierarchy
In `app/domain/exceptions.py`:
- `AppError` (base)
  - `NotFoundError`
  - `PermissionDenied`
  - `ToolFailure`
  - `VaultUnavailableError`
  - `ClassifierUnavailableError`
- Single exception handler at API boundary — maps to structured `{code, message, request_id}` response; no stack traces exposed

### 7. Dataset Fetch and Splits
- Choose one open-source repo (document in `DECISIONS.md` with rationale)
- Fetch all closed issues via GitHub API, store raw JSON in MinIO bucket `raw-data`
- Map maintainer labels → `bug | feature | docs | question` (document mapping in `DECISIONS.md`)
- Stratified split: train / val / test, where test is strictly more recent in time than train
- Save split CSVs to MinIO bucket `datasets`; log split sizes and class distribution
- Dataset hash (SHA-256 of train CSV) saved to `model_card_meta.json` for later use

---

## Acceptance Criteria
- [ ] `docker-compose up` from a fresh clone (after `.env` fill) reaches all services healthy
- [ ] `migrate` container exits 0; `api` container boots
- [ ] `api` exits with a clear error if Vault is not reachable
- [ ] Vault `GET /v1/secret/data/app` returns all seeded secrets
- [ ] A test HTTP request to `GET /health` returns `200` with `trace_id` in response headers
- [ ] Alembic `current` shows head revision
- [ ] Dataset split CSVs exist in MinIO; class distribution printed in logs
- [ ] `grep -ri 'sk-' app/` returns zero matches outside `app/infra/vault.py`

---

## Dependencies
None — this is Phase 1.

---

## Key Files to Create
- `docker-compose.yml`
- `.env.example`
- `app/__init__.py`, `app/main.py`
- `app/infra/vault.py`, `app/infra/tracing.py`, `app/infra/minio.py`, `app/infra/redis.py`
- `app/domain/exceptions.py`
- `app/api/middleware.py` (request ID + trace ID injection)
- `migrations/env.py`, `migrations/versions/0001_baseline.py`
- `scripts/seed_vault.sh`
- `scripts/fetch_dataset.py`
- `DECISIONS.md` (start it: repo choice, tracing backend choice)
