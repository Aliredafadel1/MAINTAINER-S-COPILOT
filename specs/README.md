# Maintainer's Copilot — Spec Index

5-phase breakdown of the Week 7 project. Each phase maps to one day.

| Phase | Day | Spec File | Core Deliverable |
|---|---|---|---|
| 1 | Monday | [phase1-foundations.md](phase1-foundations.md) | docker-compose stack, Vault, tracing, Alembic, dataset |
| 2 | Tuesday | [phase2-deep-learning.md](phase2-deep-learning.md) | Fine-tuned classifier, ML/LLM baselines, NER, summarizer, modelserver |
| 3 | Wednesday | [phase3-advanced-rag.md](phase3-advanced-rag.md) | Hybrid RAG, reranking, query transform, redaction layer, RAG eval |
| 4 | Thursday | [phase4-chatbot-memory-widget.md](phase4-chatbot-memory-widget.md) | Auth, chatbot, memory, React widget, CI wired |
| 5 | Friday AM | [phase5-polish-evals-ci.md](phase5-polish-evals-ci.md) | CI green, docs complete, demo ready, tag shipped |

## Grading Priorities (from the spec)
1. **Architecture is the grade** — layers respected, secrets in Vault, blob in MinIO, traces visible, logs redacted
2. **Evals are the grade** — committed thresholds, CI blocks on regression
3. **Every decision backed by a number** — all choices in `DECISIONS.md` have a metric
