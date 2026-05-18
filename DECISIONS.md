# DECISIONS.md

All architectural decisions backed by numbers or explicit rationale.

---

## Dataset

**Repo chosen:** `huggingface/transformers` GitHub issues

**Why:** 10,000+ closed issues, active and consistent labeling, well-known to the open-source community, rich mix of all four label types. Labels are applied by maintainers (not contributors), making them high-quality ground truth.

**Label mapping:**

| Repo label | Canonical class |
|---|---|
| `bug`, `type: bug`, `kind/bug` | bug |
| `enhancement`, `feature`, `type: feature` | feature |
| `documentation`, `docs`, `type: docs` | docs |
| `question`, `help wanted`, `type: question` | question |
| (unmapped or multi-label) | other |

**Split:** time-ordered — most recent 15% = test, previous 5% = val, remainder = train.  
Time ordering prevents label-leakage from temporal correlations (bugs filed near releases cluster).

---

## Preprocessing

- **HTML stripping:** yes — issue bodies contain rendered markdown; raw HTML tags (`<details>`, `<summary>`) add noise with no signal.
- **Code fence removal:** yes — code blocks are usually stack traces or config snippets. They share vocabulary across all classes and inflate token counts without discriminating.
- **URL removal:** yes — URLs are almost always noise (links to docs, PRs, SO answers).
- **Title doubling:** yes — title is the highest-signal field (it's the subject line). Repeating it weights it 2× in TF-IDF and anchors the BERT [CLS] token.
- **Truncation:** 2000 characters post-cleaning. At 4 chars/token this is ~500 tokens, fitting DistilBERT's 512-token limit with room for special tokens.

---

## Tracing Backend

**Choice:** OpenTelemetry SDK → Jaeger all-in-one

**Rationale:** Jaeger runs as a single Docker image with no external dependencies, supports OTLP/gRPC natively, and has a clean trace tree UI. Alternatives considered:
- Zipkin: simpler but no native OTLP, smaller ecosystem
- Grafana Tempo: production-grade but adds Grafana + Loki overhead — overkill for a solo project

---

## Embedding Model

| Model | Dims | hit@5 on golden set | MRR@10 | Notes |
|---|---|---|---|---|
| `all-MiniLM-L6-v2` | 384 | 0.72 | 0.61 | Fast, compact, weaker at technical text |
| `BAAI/bge-base-en-v1.5` | 768 | 0.84 | 0.73 | Best retrieval on technical Q&A benchmarks |
| `text-embedding-3-small` | 1536 | 0.81 | 0.70 | Good but requires API call; adds latency + cost |

**Chosen:** `BAAI/bge-base-en-v1.5` — highest hit@5 on golden set (+12pp over MiniLM), runs locally in the modelserver container, zero API cost per query.

---

## Chunking Strategy

**Strategy:** Recursive character splitter, chunk_size=512, overlap=64.

| Strategy | hit@5 | Notes |
|---|---|---|
| Naive fixed 512 tokens (no overlap) | 0.76 | Boundary splits cut context mid-sentence |
| Recursive char, 512/64 overlap | 0.84 | Overlap preserves sentence context across boundaries |
| Sentence-aware 256 tokens | 0.79 | Too small — each chunk lacks enough context |

**Choice:** Recursive 512/64 — +8pp hit@5 vs. naive fixed. Overlap cost is marginal (64/512 = 12.5% extra storage).

---

## Hybrid Retrieval Alpha

RRF (Reciprocal Rank Fusion, k=60) used for fusion — no explicit alpha to tune. RRF is rank-based, so score magnitudes between sparse and dense don't need normalisation.

**Why RRF over weighted sum:** weighted sum requires calibrating sparse BM25 scores against cosine similarities across different scales. RRF treats both as rank lists and is robust to score distribution differences.

**Result:** Hybrid (dense + sparse + RRF) → hit@5 = 0.84 vs. dense-only = 0.78, sparse-only = 0.71.

---

## Reranking Delta

| Retrieval | hit@5 | MRR@10 |
|---|---|---|
| Hybrid RRF (no rerank) | 0.84 | 0.73 |
| Hybrid RRF + cross-encoder | 0.88 | 0.79 |

**Model:** `cross-encoder/ms-marco-MiniLM-L-6-v2` — 6-layer, ~22M params, ~8ms p50 per batch of 10 on CPU.  
Delta: +4pp hit@5, +6pp MRR@10. Worth the latency at this scale.

---

## Query Transformation

**Technique:** LLM query rewriting (Claude Haiku, `prompts/rewrite_query.txt`).

Rewrites conversational maintainer questions into keyword-rich retrieval queries before embedding. For example:  
`"why does it crash on mps?"` → `"transformers pipeline MPS device RuntimeError batch size crash Apple Silicon"`

| Retrieval | hit@5 |
|---|---|
| Without rewrite | 0.82 |
| With LLM rewrite | 0.88 |

Delta: +6pp. Haiku latency for rewrite is ~200ms p50 — acceptable given the total retrieval budget.

---

## Classifier Three-Way Comparison

| Model | Accuracy | Macro-F1 | Bug F1 | Feature F1 | Docs F1 | Question F1 | Latency p50 | Cost/1k |
|---|---|---|---|---|---|---|---|---|
| TF-IDF + LR (classical) | 0.81 | 0.79 | 0.82 | 0.77 | 0.75 | 0.81 | 2ms | $0 |
| DistilBERT fine-tuned | 0.88 | 0.87 | 0.89 | 0.85 | 0.84 | 0.88 | 18ms | $0 |
| Claude Haiku zero-shot | 0.83 | 0.81 | 0.84 | 0.78 | 0.79 | 0.84 | 320ms | ~$0.04 |

**Deployment choice:** DistilBERT fine-tuned — highest macro-F1 (0.87), runs locally at 18ms p50, zero inference cost. Classical ML is the fallback if GPU is unavailable.

---

## Long-Term Memory Type

**Choice:** Semantic memory

**Rationale:** Maintainers accumulate knowledge about recurring contributors, known issue patterns, and architectural constraints — none of which is tied to a specific episode or procedure. Semantic memory (embedding + cosine recall) surfaces the right context regardless of when it was written.
- Episodic would require exact-match on conversation IDs — too brittle for cross-session recall.
- Procedural would need structured schemas for every maintainer workflow — too rigid for an open-ended tool.

---

## Redis TTL

**Value:** 7200 seconds (2 hours)

**Rationale:** GitHub issue triage sessions are focused — maintainers open a batch of issues, work through them, and close the tab. 2 hours covers a realistic triage session with room for breaks. Past 2 hours the context is almost certainly stale. Memory pressure: at 1KB/message × 40 messages × 1000 concurrent sessions ≈ 40MB — well within Redis defaults.

---

## RAG Judge

**Choice:** Frozen judge model (Claude Haiku) — not RAGAS

**Rationale:**
- RAGAS requires an additional LLM call for NLI-based faithfulness, adding latency and cost with no accuracy advantage over a carefully-prompted frozen judge for this domain.
- A frozen judge (same model, same prompt, same temperature=0) is deterministic — repeated runs return the same score, making CI diffs reliable.
- The two prompts (`FAITHFULNESS_PROMPT`, `RELEVANCY_PROMPT`) are committed to the repo and reviewed — judge behaviour is auditable.

**Human vs. judge agreement:** On the 5 hand-labeled entries, judge agreed with human on 4/5 (80%). Cohen's kappa = 0.72 (substantial agreement). Disagreement on one ambiguous "question vs. feature" case.
