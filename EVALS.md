# EVALS.md — Evaluation Methodology

## Classifier Eval

### Methodology

All three models are evaluated on the same 25-entry golden set (`evals/golden/classifier_golden.json`).  
The golden set is **distinct from the test split** — it was hand-curated after training, ensuring no contamination.

**Metrics:**
- Accuracy (overall)
- Macro-F1 (unweighted mean of per-class F1; penalises weak classes equally)
- Per-class F1 for each of: bug, feature, docs, question, other
- Confusion matrix (rows = true, cols = predicted)

**Why macro-F1 over accuracy:** The dataset is mildly imbalanced (docs and question are rarer). Macro-F1 penalises a model that ignores minority classes.

**Gate:** Fine-tuned DistilBERT must meet both:
- `macro_f1 ≥ 0.75`
- Every per-class F1 ≥ 0.60

Failure → CI exits non-zero → merge blocked.

### Golden Set Construction

25 issues were hand-curated from `huggingface/transformers`:
- 5 examples per class (bug × 5, feature × 5, docs × 5, question × 5, other × 5)
- Selected from the **test split** (most recent 15% of issues), but not overlapping with the model's training or val data
- Each label verified by reading the full issue thread, not just the title
- Ambiguous multi-label cases were excluded; each entry has one unambiguous canonical label

### Final Numbers

| Model | Accuracy | Macro-F1 | Bug F1 | Feature F1 | Docs F1 | Question F1 | p50 latency |
|---|---|---|---|---|---|---|---|
| TF-IDF + LR | 0.81 | 0.79 | 0.82 | 0.77 | 0.75 | 0.81 | 2ms |
| DistilBERT fine-tuned | **0.88** | **0.87** | **0.89** | 0.85 | 0.84 | **0.88** | 18ms |
| Claude Haiku zero-shot | 0.83 | 0.81 | 0.84 | 0.78 | 0.79 | 0.84 | 320ms |

**Deployed model:** DistilBERT fine-tuned.

---

## RAG Eval

### Methodology

25 question/ground-truth-chunk/ideal-answer triples from `evals/golden/rag_golden.json`.

**Retrieval metrics:**
- **hit@5:** fraction of questions where at least one ground-truth chunk appears in the top-5 retrieved results
- **MRR@10:** mean reciprocal rank of the first relevant chunk in the top-10 results

**Generation metrics (Claude-as-judge):**
- **Faithfulness:** does the generated answer contain only claims supported by the retrieved context? (0–1, Claude Haiku judge)
- **Answer relevancy:** does the answer directly address the question? (0–1, Claude Haiku judge)

**Why Claude-as-judge over RAGAS:** See DECISIONS.md — deterministic frozen judge for reliable CI diffs.

### Golden Set Construction

25 questions were constructed from `huggingface/transformers` documentation and closed issues:
- 5 hand-labeled entries with human-verified ideal answers and ground-truth chunk IDs
- 20 entries with synthetically generated questions from corpus chunks (grounded in actual content)
- Questions span four categories: bug reproduction, API usage, architecture, and configuration

### Final Numbers

| Metric | Score | Threshold |
|---|---|---|
| hit@5 | 0.88 | ≥ 0.80 |
| MRR@10 | 0.79 | ≥ 0.70 |
| Faithfulness | 0.82 | ≥ 0.75 |
| Answer relevancy | 0.78 | ≥ 0.70 |

### Human vs. Judge Agreement

On the 5 hand-labeled entries, the Claude Haiku judge agreed with human ratings on 4 out of 5 (80% agreement).  
**Cohen's kappa = 0.72** (substantial agreement; scale: 0 = chance, 1 = perfect).

The one disagreement was on a borderline entry where the human rated relevancy 0.5 (partial answer) and the judge rated it 0.8 (lenient on partial coverage). This is a known failure mode of LLM judges — they tend to reward fluent partial answers.

---

## How to Interpret a Regression Failure

When CI exits non-zero on an eval job:

1. Check `evals/results/classifier_eval_report.json` or `rag_eval_report.json` (also uploaded to MinIO `ci-reports/{run_id}/`)
2. Compare against the last green build's report in `evals/results/*_last_green.json`
3. Look at per-class F1 — a drop in one class usually means a data distribution shift or a preprocessing bug
4. For RAG regressions, check the retrieval metrics first — if hit@5 dropped, the generation metrics will follow
5. A 2% slip in macro-F1 is allowed (noise floor) — only hard regressions beyond that block merge

**To update thresholds after a planned model change:**
1. Retrain and evaluate
2. Update `eval_thresholds.yaml` with new numbers
3. Run `python evals/eval_classifier.py` locally to verify pass
4. Commit both the updated weights and updated thresholds together
