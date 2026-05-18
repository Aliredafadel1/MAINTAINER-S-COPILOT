# RUNBOOK — Maintainer's Copilot

## Starting the Stack from a Fresh Clone

```bash
# 1. Copy env template
cp .env.example .env
# Edit .env — set VAULT_ROOT_TOKEN to any string (e.g. "devroot")

# 2. Start everything (boot order enforced by depends_on + healthchecks)
docker compose up --build

# Wait for "startup_complete" in the api logs (~60s on first pull)
```

Services and their ports:

| Service | URL |
|---|---|
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Streamlit UI | http://localhost:8501 |
| Jaeger tracing UI | http://localhost:16686 |
| MinIO console | http://localhost:9001 (minioadmin / minioadmin) |
| Vault UI | http://localhost:8200 (token from .env) |
| Demo host | http://localhost:3000 |

---

## Seeding Vault

Vault is seeded automatically by the `seed-vault` container on first `docker compose up`. To re-seed manually:

```bash
docker compose run --rm seed-vault
# Or directly:
python scripts/seed_vault.py
```

Vault secrets live at `secret/data/app`. To inspect them:

```bash
docker compose exec vault vault kv get -mount=secret app
```

---

## Running Eval Suites Locally

### Classifier eval (requires modelserver running)

```bash
# With Docker Compose stack up:
python evals/eval_classifier.py --modelserver-url http://localhost:8001

# Skip MinIO upload (for quick local runs):
python evals/eval_classifier.py --skip-minio
```

### RAG eval (requires api + PostgreSQL running)

```bash
ANTHROPIC_API_KEY=sk-... python evals/eval_rag.py
```

Results are written to `evals/results/`.

---

## Training the Classifier

```bash
# 1. Fetch dataset (requires GITHUB_TOKEN in env or Vault)
python scripts/fetch_dataset.py

# 2. Preprocess
python scripts/preprocess.py

# 3. Train DistilBERT (GPU recommended; ~20min on A10G)
python scripts/train_classifier.py

# 4. Train classical baseline (fast, CPU fine)
python scripts/train_classical.py

# 5. Run LLM baseline eval
python scripts/eval_llm_baseline.py
```

Model artifacts upload to MinIO `model-artifacts/` automatically.

---

## Ingesting the Corpus

```bash
# Requires api + PostgreSQL + modelserver running
python scripts/ingest_corpus.py --source-type docs --path /path/to/docs/
python scripts/ingest_corpus.py --source-type issue --path data/issues_train.jsonl
```

---

## Accessing the Streamlit UI

1. Open http://localhost:8501
2. Register an account (first user automatically gets admin role)
3. Use the sidebar to navigate: Chat → Memory → Widgets → Audit Log

---

## Accessing the Demo Host

Open http://localhost:3000

Replace `YOUR_WIDGET_ID` in `demo/host/index.html` with a real widget ID from the admin UI.

---

## Adding a New Widget (Admin Steps)

1. Log in to Streamlit UI (admin account)
2. Navigate to **Widgets** page
3. Enter widget name and allowed origins (e.g. `https://myproject.com`)
4. Copy the generated `<script>` tag
5. Paste into your site's HTML

To add via API directly:

```bash
curl -X POST http://localhost:8000/widgets \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Widget", "allowed_origins": ["https://myproject.com"]}'
```

---

## Common Failure Modes

### `api` exits immediately with "vault_failed"

**Cause:** Vault not yet healthy or VAULT_ROOT_TOKEN wrong.  
**Fix:** Check `docker compose logs vault`. Ensure `VAULT_ROOT_TOKEN` in `.env` matches what Vault was initialized with. Run `docker compose restart seed-vault api`.

### `api` exits with "classifier_weights_missing"

**Cause:** `model_card.json` references a weights file that doesn't exist locally.  
**Fix:** Run `python scripts/train_classifier.py` to train and upload, or pull from MinIO:
```bash
python -c "
from app.infra import vault, minio_client
vault.load_secrets(); minio_client.init()
minio_client.client().fget_object('model-artifacts', 'distilbert/model.pt', 'model.pt')
"
```

### `migrate` container fails with "connection refused"

**Cause:** PostgreSQL not yet ready.  
**Fix:** The `migrate` service has `depends_on: postgres: condition: service_healthy`. If it still fails, increase the pg healthcheck `start_period` in `docker-compose.yml`.

### Modelserver OOM on CPU

**Cause:** All three PyTorch models loaded simultaneously (~1.5GB RAM).  
**Fix:** Set `MODELSERVER_DISABLE_RERANK=1` in `.env` to skip the cross-encoder on memory-constrained machines. This disables reranking but keeps classification and embeddings.

### Redis "connection refused" in logs

**Cause:** Redis not yet started.  
**Fix:** `docker compose restart redis api`. Check `docker compose ps` to verify Redis is healthy.

### Widget blocked in iframe (CSP error in browser console)

**Expected behaviour for disallowed origins.** To allow a new origin:
```bash
curl -X PATCH http://localhost:8000/widgets/{widget_id} \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"allowed_origins": ["https://allowed.com", "https://new.com"]}'
```
