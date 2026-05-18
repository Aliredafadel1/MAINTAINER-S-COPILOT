# Phase 2 — Deep Learning Track
**Day:** Tuesday  
**Goal:** Fine-tuned transformer classifier, classical ML and LLM baselines, three-way comparison, NER tool, summarization tool — all behind a `modelserver` FastAPI service.

---

## Deliverables

### 1. Data Preprocessing Pipeline
In `scripts/preprocess.py`:
- Clean issue text: strip HTML, normalize whitespace, truncate to max token budget
- Remove duplicates and near-duplicates (Jaccard or MinHash)
- Lowercase, remove markdown code fences (configurable — log your choice in `DECISIONS.md`)
- Output: preprocessed CSVs in MinIO `datasets/` alongside the raw splits
- Defend every preprocessing choice in `DECISIONS.md`

### 2. Fine-Tuned Transformer Classifier
- Base model: a small encoder — `distilbert-base-uncased` or `roberta-base` (document choice)
- Task: 4-class classification — `bug | feature | docs | question`
- Training tracked with a real run logger (MLflow or Weights & Biases — pick one, document in `DECISIONS.md`)
- **Freeze policy:** document which layers are frozen and why in `DECISIONS.md`
- Save artifact to MinIO `models/classifier/`:
  - `pytorch_model.bin` (or `model.safetensors`)
  - `config.json`, `tokenizer/`
  - `model_card.json` with: architecture, hyperparameters, training data hash (SHA-256 of train CSV), final metrics (accuracy, macro-F1, per-class F1)
- SHA-256 of weights file written to `model_card.json` — `api` checks this at boot

### 3. Classical ML Baseline
In `scripts/train_classical.py`:
- TF-IDF features + Logistic Regression (or LinearSVC)
- Same train/val/test splits as the transformer
- Report: accuracy, macro-F1, per-class F1, inference latency (median over test set), estimated cost per 1k predictions
- Save results to `evals/results/classical_results.json`

### 4. LLM Baseline
In `scripts/eval_llm_baseline.py`:
- Zero-shot or few-shot prompt against the same test split
- Model: any available LLM (document in `DECISIONS.md`)
- Same metrics + latency + cost
- Save results to `evals/results/llm_baseline_results.json`

### 5. Three-Way Comparison
In `DECISIONS.md`, a table with all three models:

| Model | Accuracy | Macro-F1 | Bug F1 | Feature F1 | Docs F1 | Question F1 | Latency (p50) | Cost/1k |
|---|---|---|---|---|---|---|---|---|
| Classical ML | | | | | | | | |
| Fine-tuned XFMR | | | | | | | | |
| LLM baseline | | | | | | | | |

- Defend your deployment choice (which model ships in `modelserver`) with one clear sentence

### 6. NER Tool
In `app/services/ner.py`:
- Extract code-shaped entities: package names, version strings, error codes, file paths, GitHub issue/PR references, stack trace identifiers
- Integration-only: use `spacy` with a pre-trained model + custom regex patterns, OR a small HuggingFace NER pipeline
- Input: raw issue text string
- Output: `{"entities": [{"text": str, "label": str, "start": int, "end": int}]}`
- Document model/library choice in `DECISIONS.md`

### 7. Summarization Tool
In `app/services/summarizer.py`:
- Input: issue thread (title + body + top N comments)
- Output: 2–4 sentence summary
- Implementation: LLM-driven (prompt in `prompts/summarize_issue.txt`) OR pre-trained model (e.g., `facebook/bart-large-cnn`)
- Document choice in `DECISIONS.md`

### 8. Model Server (`modelserver`)
FastAPI app at `services/modelserver/`:
- `POST /classify` — runs fine-tuned classifier, returns `{label, confidence, probabilities}`
- `POST /ner` — runs NER tool, returns entity list
- `POST /summarize` — runs summarizer, returns summary string
- All three endpoints emit OpenTelemetry spans with: model name, input length (tokens), latency, output (after redaction)
- Returns structured errors (no stack traces) using the shared exception hierarchy
- Loads model weights from MinIO at startup; refuses to start if weights SHA-256 doesn't match `model_card.json`

---

## Acceptance Criteria
- [ ] `POST /classify` on the test split reproduces the macro-F1 reported in `model_card.json` (±0.01)
- [ ] `model_card.json` exists in MinIO with all required fields
- [ ] `POST /ner` extracts at least version strings and package names from a sample issue
- [ ] `POST /summarize` returns a coherent 2–4 sentence summary
- [ ] All three endpoints appear as spans in the tracing UI
- [ ] `evals/results/classical_results.json` and `evals/results/llm_baseline_results.json` exist
- [ ] Three-way comparison table in `DECISIONS.md` is filled with real numbers
- [ ] `modelserver` refuses to boot if weights SHA-256 mismatches `model_card.json`

---

## Dependencies
- Phase 1: MinIO, Vault, tracing, dataset splits, exception hierarchy

---

## Key Files to Create
- `scripts/preprocess.py`
- `scripts/train_classifier.py`
- `scripts/train_classical.py`
- `scripts/eval_llm_baseline.py`
- `services/modelserver/main.py`
- `services/modelserver/routes/classify.py`, `ner.py`, `summarize.py`
- `app/services/ner.py`, `app/services/summarizer.py`
- `evals/results/` (directory)
- `prompts/summarize_issue.txt`
- `model_card.json` (written by training script, stored in MinIO)
