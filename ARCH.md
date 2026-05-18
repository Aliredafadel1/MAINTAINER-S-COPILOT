# Architecture — Maintainer's Copilot

## System Diagram

```
Browser / Demo Host
       │
       │  HTTP (REST + SSE)
       ▼
┌──────────────────────────────────────────────────────────────┐
│                         api  :8000                           │
│  FastAPI · structlog · OpenTelemetry auto-instrumentation    │
│                                                              │
│  Routes                                                      │
│    /auth      register · login · invite                      │
│    /chat      SSE stream · conversation history              │
│    /rag       search · answer                                │
│    /memory    list · delete                                  │
│    /widgets   CRUD · config (CSP frame-ancestors)            │
│    /audit     admin log                                      │
│    /health    liveness                                       │
│    /static    widget.js bundle                               │
│                                                              │
│  Services                                                    │
│    chatbot   → tool loop → [classify, NER, summarize,        │
│                              search_docs, write_memory]      │
│    retrieval → rewrite(LLM) → embed → dense+sparse → RRF    │
│                → rerank(cross-encoder)                       │
│    auth      → bcrypt · JWT (python-jose)                    │
│    memory    → short-term(Redis) · long-term(pgvector)       │
└──────────────┬───────────────────────────────────────────────┘
               │  httpx (internal)
               ▼
┌──────────────────────────────────────────────────────────────┐
│                    modelserver  :8001                        │
│  FastAPI · PyTorch · sentence-transformers                   │
│                                                              │
│  /classify          DistilBERT fine-tuned (shipped model)    │
│  /classify/classical  TF-IDF + LogisticRegression            │
│  /classify/llm      Claude Haiku zero-shot                   │
│  /ner               Regex NER (version, ref, path, error)    │
│  /summarize         Claude Haiku, max_tokens=256             │
│  /embed             BAAI/bge-base-en-v1.5 (768-dim)          │
│  /embed/batch       batched BGE                              │
│  /rerank            cross-encoder/ms-marco-MiniLM-L-6-v2     │
│  /health                                                     │
└──────────────┬───────────────────────────────────────────────┘
               │
       ┌───────┴──────────────────────────────┐
       │                                      │
       ▼                                      ▼
┌─────────────┐                    ┌──────────────────┐
│  Anthropic  │                    │  MinIO  :9000    │
│  Claude API │                    │  model-artifacts │
│  (Haiku /   │                    │  corpus-chunks   │
│   Sonnet)   │                    │  ci-reports      │
└─────────────┘                    └──────────────────┘

Shared infrastructure (Docker Compose):

┌─────────────────────────────────────────────────────────────┐
│  PostgreSQL 16 + pgvector  :5432                            │
│    tables: users, conversations, messages, memories,        │
│            corpus_chunks, widgets, audit_log                │
│    indexes: HNSW (memories, corpus_chunks.embedding)        │
│             GIN/tsvector (corpus_chunks FTS)                │
├─────────────────────────────────────────────────────────────┤
│  Redis 7  :6379                                             │
│    short-term conversation state (TTL 7200s, 40-turn cap)   │
├─────────────────────────────────────────────────────────────┤
│  Vault (HashiCorp)  :8200                                   │
│    KV v2 at secret/data/app                                 │
│    all app secrets; api exits 1 if unreachable              │
├─────────────────────────────────────────────────────────────┤
│  Jaeger all-in-one  :16686 (UI)  :4317 (OTLP/gRPC)         │
│    receives traces from api + modelserver                   │
└─────────────────────────────────────────────────────────────┘

Deployment-time containers (run once, then exit):
  seed-vault   → seeds Vault KV with secrets from env
  migrate      → pulls DB_PASSWORD from Vault, runs alembic upgrade head
```

## Layer Rules

| Layer | Owns | Must not |
|---|---|---|
| `app/api/routes/` | HTTP request parsing, response serialisation | contain business logic |
| `app/services/` | Business logic, orchestration | import SQLAlchemy models directly |
| `app/repositories/` | All database queries | contain business logic |
| `app/infra/` | External clients (Vault, DB, Redis, MinIO, LLM, OTel) | import from services or routes |
| `app/domain/` | ORM models, exceptions | import from any other app layer |

## Boot Order

```
vault  →  seed-vault  →  migrate  →  api
                                  →  modelserver
```

The `api` container performs these checks on startup (exits 1 on failure):
1. Vault reachable and secrets loaded
2. Tracing backend configured
3. Database reachable
4. Redis reachable
5. MinIO reachable
6. All `eval_thresholds.yaml` values > 0
7. Classifier weights present and SHA-256 matches `model_card.json`
