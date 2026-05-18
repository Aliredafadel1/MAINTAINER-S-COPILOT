# Phase 5 — Polish, Evals, CI Green
**Day:** Friday AM  
**Goal:** CI fully green, all documentation complete, live demo rehearsed, every graded surface verified working end-to-end.

---

## Deliverables

### 1. Classification Eval Harness (finalize)
File: `evals/eval_classifier.py`
- Runs the 25-issue hand-curated golden set (separate from the test split) through all three models
- **Metrics:** macro-F1, per-class F1, confusion matrix for each model
- Writes results to `evals/results/classifier_eval_report.json`
- Reads thresholds from `eval_thresholds.yaml`; exits non-zero if fine-tuned model falls below threshold
- `eval_report.json` stored in MinIO `ci-reports/{run_id}/` on every run
- Diff logic: compare against the last green build's report; block merge if any metric regressed

Golden set file: `evals/golden/classifier_golden.json`
- 25 entries: `{issue_id, text, label}` — hand-curated, distinct from the test split
- Labels verified by you, not inferred

### 2. RAG Eval Harness (finalize)
File: `evals/eval_rag.py`
- 25 question/ideal-answer/ground-truth-chunks triples from `evals/golden/rag_golden.json`
- **Retrieval:** hit@5, MRR@10
- **Generation:** faithfulness, answer relevancy (RAGAS or frozen judge — document in `DECISIONS.md`)
- **Human vs. judge agreement:** for the 5 hand-labeled entries, report % agreement or Cohen's kappa
- Writes `evals/results/rag_eval_report.json`
- Exits non-zero on threshold regression

### 3. `eval_thresholds.yaml` — Finalized
```yaml
classifier:
  macro_f1: 0.75          # example — set your real number
  min_per_class_f1: 0.60

rag:
  hit_at_5: 0.80
  mrr_at_10: 0.70
  faithfulness: 0.75
  answer_relevancy: 0.70
```
- All thresholds must be > 0 (api refuses to boot if any threshold is zero or missing)
- Committed to the repo — these are the CI gates

### 4. CI — Fully Green
`.github/workflows/ci.yml` passes on every commit:
- [ ] `ruff check app/` — zero lint errors
- [ ] `mypy app/` — zero type errors
- [ ] `docker-compose build` — all images build
- [ ] `docker-compose up` smoke test — all services healthy, `GET /health` returns 200
- [ ] `pytest evals/eval_classifier.py` — passes thresholds
- [ ] `pytest evals/eval_rag.py` — passes thresholds
- [ ] `pytest tests/test_redaction.py` — passes
- [ ] `eval_report.json` stored to MinIO, diffed against last green build

### 5. Refuse-to-Boot Checklist (`api`)
Verify all boot guards are in place in `app/main.py` startup:
- [ ] Vault unreachable → `VaultUnavailableError`, container exits 1
- [ ] Classifier weights missing from MinIO → exits 1
- [ ] Weights SHA-256 mismatches `model_card.json` → exits 1
- [ ] Tracing backend misconfigured → exits 1
- [ ] Any threshold in `eval_thresholds.yaml` is 0 or missing → exits 1

### 6. Observability — Final Wiring Audit
Walk through every service and verify:
- [ ] Every LLM call is a span with: model name, token counts (prompt + completion), latency
- [ ] Every tool call is a child span: tool name, inputs (redacted), outputs (redacted), latency
- [ ] Every RAG retrieval is a span: query (redacted), number of results, reranker score
- [ ] Trace ID present in every structured log line for the same request
- [ ] One complete conversation trace visible in the tracing UI showing the full tree

### 7. Required Documentation
All files committed to the repo root:

**`ARCH.md`**
- Architecture diagram (ASCII is fine)
- Service map: what each container does, what it calls
- Layer rules: which layer owns what

**`DECISIONS.md`**
- Dataset choice and rationale
- Label mapping (maintainer labels → bug/feature/docs/question)
- Preprocessing choices with justification
- Embedding model comparison (numbers from golden set)
- Chunking strategy choice and hit-rate delta
- Hybrid retrieval alpha tuning
- Reranking delta
- Query transformation technique and delta
- Three-way classifier comparison table
- Deployment choice for classifier (which model ships and why)
- Tracing backend choice
- Long-term memory type choice (episodic/semantic/procedural) and rationale
- Redis TTL value and rationale
- RAGAS vs. judge choice for RAG eval

**`RUNBOOK.md`**
- How to start the stack from a fresh clone
- How to run eval suites locally
- How to seed Vault
- How to access the Streamlit UI and the demo host
- How to add a new widget (admin steps)
- Common failure modes and fixes (Vault unreachable, model weights missing, etc.)

**`EVALS.md`**
- Eval methodology for both suites
- Golden set construction process (how you picked the 25 examples)
- Final numbers for both suites
- Human vs. judge agreement result
- How to interpret a regression failure

**`SECURITY.md`**
- Redaction patterns and rationale for each
- Why these patterns and not others (what shows up in real issue text)
- Test coverage for redaction
- CORS and CSP allowlisting mechanism
- Vault secret rotation policy (even if just described, not automated)

### 8. Submission Block
Fill in `README.md` with the submission block from the spec:
```
Project 7 - [Name]
Repo: [GitHub URL]
Tag: v0.1.0-week7
Dataset: [chosen repo] issues, [N train / N val / N test]
Classification — Classical: F1=[n] | Fine-tuned: F1=[n] | LLM: F1=[n]
Deployment choice: [model] — because [one line]
Embedding model: [name] — chosen because [one line]
RAG — hit@5=[n] | MRR@10=[n] | Faithfulness=[n] | Answer relevancy=[n]
Long-term memory type: [episodic | semantic | procedural]
Tracing backend: [name] — chosen because [one line]
Widget bundle size: [n] KB (gzipped)
LLM: [provider + model]
README contains: ARCH.md, DECISIONS.md, RUNBOOK.md, EVALS.md, SECURITY.md
```

### 9. Git Tag
```bash
git tag v0.1.0-week7
git push origin v0.1.0-week7
```

### 10. Friday Demo Script (10 minutes)
Rehearse this order:
1. **(1 min)** `docker-compose up` from a clean state — all services healthy
2. **(2 min)** Classify an issue, show the trace tree in the tracing UI
3. **(1 min)** Ask a RAG question in the chatbot, show retrieved chunks
4. **(1 min)** Use `write_memory`, close and reopen a conversation, show cross-conversation recall
5. **(1 min)** Show widget loading in `demo/host/` (allowed origin)
6. **(1 min)** Show widget blocked on a disallowed origin (browser console + network tab)
7. **(1 min)** Open tracing UI — walk a full conversation trace tree including one error span
8. **(1 min)** Show CI badge green; open `eval_report.json` diff
9. **(1 min)** Architecture boundary test: add a new endpoint or tool live (this is the grader's test)

---

## Acceptance Criteria
- [ ] `docker-compose up` from a fresh clone is fully green
- [ ] All 5 CI jobs pass on the final commit
- [ ] `v0.1.0-week7` tag pushed to GitHub
- [ ] `ARCH.md`, `DECISIONS.md`, `RUNBOOK.md`, `EVALS.md`, `SECURITY.md` all present and complete
- [ ] Submission block in `README.md` filled with real numbers
- [ ] All refuse-to-boot guards verified (test by stopping Vault and restarting `api`)
- [ ] Every graded metric in `DECISIONS.md` backed by a real number, not a placeholder

---

## Dependencies
- All previous phases complete
- Both golden sets finalized (25 entries each)
- Widget bundle built and measured

---

## Key Files to Finalize
- `evals/eval_classifier.py`
- `evals/golden/classifier_golden.json`
- `eval_thresholds.yaml`
- `.github/workflows/ci.yml`
- `ARCH.md`, `DECISIONS.md`, `RUNBOOK.md`, `EVALS.md`, `SECURITY.md`
- `README.md` (submission block)
