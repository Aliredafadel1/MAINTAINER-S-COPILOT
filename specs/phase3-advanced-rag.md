# Phase 3 — Advanced RAG
**Day:** Wednesday  
**Goal:** A retrieval pipeline that beats naive fixed-size + pure-dense baseline on a 25-example golden set, plus a redaction layer and exception handling hardened across all services.

---

## Deliverables

### 1. RAG Corpus
Two sources, ingested into the vector store:
1. **Project docs** — README, CONTRIBUTING, wiki pages, any markdown in the chosen repo
2. **Resolved issues (held-out slice)** — issues with maintainer answers that were NOT used in classifier training

Ingest script at `scripts/ingest_corpus.py`:
- Fetches docs and held-out issues
- Runs preprocessing pipeline (reuse from Phase 2)
- Chunks, embeds, and upserts into pgvector
- Stores raw chunks + metadata in MinIO `rag-corpus/` for auditability
- **Held-out issues must not overlap with classifier train/val/test splits** — assert this in the script

### 2. Chunking Strategy
Not naive fixed-size. Choose one:
- **Recursive character splitter** with overlap, tuned to your corpus
- **Sentence-window chunking** — embed sentence, store surrounding window
- **Document-aware chunking** — split on markdown headings / issue sections

Document choice and chunk size in `DECISIONS.md`, justified with a retrieval hit-rate number vs. naive fixed-size on your golden set.

### 3. Embedding Model Choice
- Evaluate at least two embedding models on your 25-example RAG golden set (hit@5 or MRR@10)
- Choose the better one; document both numbers in `DECISIONS.md`
- Suggested candidates: `text-embedding-3-small`, `BAAI/bge-base-en-v1.5`, `sentence-transformers/all-MiniLM-L6-v2`
- Embeddings stored in pgvector `memories` table (extend from Phase 1 migration) with `source_type`, `source_id`, `chunk_index` metadata columns

### 4. Hybrid Retrieval
In `app/services/retrieval.py`:
- **Dense:** pgvector cosine similarity search (top-k)
- **Sparse:** BM25 over the same corpus (use `rank_bm25` or a Postgres full-text search index)
- **Fusion:** Reciprocal Rank Fusion (RRF) with a tunable `alpha` weight
- Tune `alpha` on the golden set; report best value in `DECISIONS.md`

### 5. Cross-Encoder Reranking
- After hybrid fusion, rerank top-k results with a cross-encoder
- Model: `cross-encoder/ms-marco-MiniLM-L-6-v2` (or equivalent small model)
- Report reranking's delta on hit@5 vs. hybrid-only on the golden set in `DECISIONS.md`

### 6. Query Transformation
Choose one technique and implement it:
- **HyDE (Hypothetical Document Embeddings):** generate a hypothetical answer, embed it, retrieve with that embedding
- **Query rewriting:** LLM rewrites the user question to be more retrieval-friendly (prompt in `prompts/rewrite_query.txt`)
- **Step-back prompting:** LLM generates an abstract version of the question first

Document choice and hit@5 delta on golden set in `DECISIONS.md`.

### 7. Metadata Filtering
- Every chunk stored with metadata: `source_type` (`docs` | `issue`), `source_id`, `created_at`, `labels` (for issues)
- Retrieval accepts optional filter params: `source_type`, `date_range`, `labels`
- Used by the chatbot to scope RAG to docs-only or issues-only when context warrants

### 8. RAG Golden Set
File: `evals/golden/rag_golden.json`
- 25 triples: `{question, ideal_answer, ground_truth_chunk_ids}`
- Sourced from held-out resolved issues — real maintainer questions and their answers
- **Hand-label 5 of the 25 yourself** (mark with `"hand_labeled": true`)

### 9. RAG Eval Harness
File: `evals/eval_rag.py`:
- Runs all 25 questions through the full retrieval pipeline
- **Retrieval metrics:** hit@5, MRR@10
- **Generation metrics:** faithfulness, answer relevancy (RAGAS or frozen judge model — document choice in `DECISIONS.md`)
- For hand-labeled 5: report agreement between your labels and the judge (Cohen's kappa or % agreement)
- Writes `evals/results/rag_eval_report.json`
- Reads thresholds from `eval_thresholds.yaml`; exits non-zero if any metric is below threshold

### 10. Redaction Layer
In `app/infra/redaction.py`:
- Runs before any log line, trace span, or memory write leaves the service boundary
- Patterns to redact (define and document in `SECURITY.md`):
  - API keys / tokens (regex: `(sk|gh[ps]|xox[bpoa])-[A-Za-z0-9\-_]{10,}`)
  - Email addresses
  - GitHub tokens (`ghp_...`, `ghs_...`)
  - Passwords in structured fields
  - Stack trace file paths with absolute system paths
- **Tested explicitly:** `tests/test_redaction.py` asserts a message containing a fake API key `sk-test-1234567890` never appears unredacted in logs, spans, or memory writes
- Used by every service via a shared `redact(text: str) -> str` function

### 11. Exception Handling Refactor
- Extend `app/domain/exceptions.py` with `RAGError`, `EmbeddingError`, `RetrievalError`
- `modelserver` and `api` both use the single exception handler pattern from Phase 1
- Tool failures in the chatbot are caught and recovered: if retrieval fails, the LLM gets a clear tool-error message and responds gracefully — no 500s propagate to the user

---

## Acceptance Criteria
- [ ] `evals/eval_rag.py` runs and exits 0 with hit@5 ≥ baseline (naive fixed-size + pure-dense)
- [ ] `DECISIONS.md` has retrieval numbers for: chunking choice, embedding model choice, hybrid alpha, reranking delta, query transformation delta
- [ ] `evals/golden/rag_golden.json` has 25 entries, 5 marked `hand_labeled: true`
- [ ] Redaction test passes: `pytest tests/test_redaction.py`
- [ ] A log line containing `sk-test-1234567890` is fully redacted in output
- [ ] Metadata filter works: querying with `source_type=docs` returns only doc chunks
- [ ] Retrieved chunks per conversation stored in MinIO `rag-snapshots/`

---

## Dependencies
- Phase 1: pgvector, MinIO, Vault, tracing, redaction scaffold
- Phase 2: preprocessed corpus, held-out issue slice identified

---

## Key Files to Create
- `scripts/ingest_corpus.py`
- `app/services/retrieval.py`
- `app/infra/redaction.py`
- `evals/eval_rag.py`
- `evals/golden/rag_golden.json`
- `eval_thresholds.yaml` (scaffold with RAG thresholds)
- `prompts/rewrite_query.txt` (or `prompts/hyde_prompt.txt`)
- `tests/test_redaction.py`
- `SECURITY.md` (start it: redaction patterns and rationale)
- New Alembic migration: add metadata columns to embeddings table
