# Maintainer's Copilot

An AI-powered triage assistant for open-source maintainers. Classifies issues, searches the project corpus, summarizes threads, and remembers context across sessions — all in an embeddable widget.

---

## Submission Block

```
Project 7 - Maintainer's Copilot
Repo: https://github.com/<your-github-username>/maintainers-copilot
Tag: v0.1.0-week7
Dataset: huggingface/transformers issues — 7,200 train / 600 val / 1,400 test
Classification — Classical: F1=0.79 | Fine-tuned: F1=0.87 | LLM: F1=0.81
Deployment choice: DistilBERT fine-tuned — best macro-F1 (0.87) at 18ms p50, zero inference cost
Embedding model: BAAI/bge-base-en-v1.5 — highest hit@5 (0.84) on golden set vs. MiniLM and text-embedding-3-small
RAG — hit@5=0.88 | MRR@10=0.79 | Faithfulness=0.82 | Answer relevancy=0.78
Long-term memory type: semantic
Tracing backend: Jaeger all-in-one — single Docker image, native OTLP/gRPC, clean trace tree UI
Widget bundle size: ~180 KB (gzipped ~58 KB)
LLM: Anthropic Claude — Haiku for tools/classification, Sonnet available for richer responses
README contains: ARCH.md, DECISIONS.md, RUNBOOK.md, EVALS.md, SECURITY.md
```

---

## Quick Start

```bash
cp .env.example .env       # set VAULT_ROOT_TOKEN
docker compose up --build  # ~60s on first pull
open http://localhost:8501 # Streamlit UI
```

See [RUNBOOK.md](RUNBOOK.md) for full instructions.

---

## Documentation

| Doc | Contents |
|---|---|
| [ARCH.md](ARCH.md) | ASCII architecture diagram, service map, layer rules, boot order |
| [DECISIONS.md](DECISIONS.md) | Every architectural decision with supporting numbers |
| [RUNBOOK.md](RUNBOOK.md) | Start stack, seed Vault, run evals, add widgets, failure modes |
| [EVALS.md](EVALS.md) | Eval methodology, golden set construction, final numbers, human/judge agreement |
| [SECURITY.md](SECURITY.md) | Redaction patterns, secrets management, Vault rotation, CSP/CORS |

---

## Stack

- **API:** FastAPI + SQLAlchemy 2.0 async + asyncpg
- **DB:** PostgreSQL 16 + pgvector (HNSW for ANN, GIN for FTS)
- **Cache:** Redis 7 (short-term conversation memory)
- **Secrets:** HashiCorp Vault KV v2
- **Blob storage:** MinIO (model artifacts, eval reports, corpus chunks)
- **Tracing:** OpenTelemetry → Jaeger all-in-one
- **ML:** DistilBERT (HuggingFace Trainer) + TF-IDF + LogisticRegression
- **Embeddings:** BAAI/bge-base-en-v1.5 (768-dim)
- **Reranker:** cross-encoder/ms-marco-MiniLM-L-6-v2
- **LLM:** Anthropic Claude (Haiku + Sonnet)
- **UI:** Streamlit admin + React widget (Vite IIFE bundle)
- **CI:** GitHub Actions — lint, type-check, tests, widget build, eval gates
