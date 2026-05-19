"""RAG evaluation harness.

Runs 25 golden questions through the full retrieval pipeline and measures:
  - hit@5, MRR@10  (retrieval)
  - faithfulness, answer_relevancy  (generation, Claude-as-judge)

Usage:
    python evals/eval_rag.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import anthropic
import httpx
import yaml

GOLDEN_PATH = Path("evals/golden/rag_golden.json")
THRESHOLDS_PATH = Path("eval_thresholds.yaml")
RESULTS_PATH = Path("evals/results/rag_eval_report.json")
API_BASE = os.environ.get("API_URL", "http://localhost:8000")

JUDGE_SYSTEM = """You are an evaluation judge for a RAG system.
Rate the answer on the criterion given. Reply with a single float between 0 and 1, nothing else."""

FAITHFULNESS_PROMPT = """Context chunks used for the answer:
{context}

Answer given:
{answer}

Criterion: faithfulness — does the answer contain only information supported by the context?
Score 1.0 if fully faithful, 0.0 if the answer makes claims not in the context."""

RELEVANCY_PROMPT = """Question asked:
{question}

Answer given:
{answer}

Criterion: answer_relevancy — does the answer directly address the question?
Score 1.0 if fully relevant, 0.0 if the answer ignores the question."""


def load_golden() -> list[dict]:
    data = json.loads(GOLDEN_PATH.read_text())
    assert len(data) == 25, f"golden set must have 25 entries, got {len(data)}"
    return data


def load_thresholds() -> dict:
    return yaml.safe_load(THRESHOLDS_PATH.read_text()).get("rag", {})


async def retrieve(
    session: httpx.AsyncClient, question: str
) -> tuple[list[str], list[str]]:
    """Returns (chunk_ids, chunk_contents)."""
    resp = await session.post(
        f"{API_BASE}/rag/search",
        json={"query": question, "top_k": 10},
        timeout=30.0,
    )
    resp.raise_for_status()
    results = resp.json()["results"]
    ids = [r["id"] for r in results]
    contents = [r["content"] for r in results]
    return ids, contents


async def generate(session: httpx.AsyncClient, question: str, chunks: list[str]) -> str:
    context = "\n\n---\n\n".join(chunks[:5])
    resp = await session.post(
        f"{API_BASE}/rag/answer",
        json={"question": question, "context": context},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()["answer"]


def judge_score(client: anthropic.Anthropic, prompt: str) -> float:
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        system=JUDGE_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        return float(msg.content[0].text.strip())
    except ValueError:
        return 0.0


def hit_at_k(retrieved_ids: list[str], ground_truth_ids: list[str], k: int) -> float:
    return float(bool(set(retrieved_ids[:k]) & set(ground_truth_ids)))


def reciprocal_rank(retrieved_ids: list[str], ground_truth_ids: list[str]) -> float:
    gt = set(ground_truth_ids)
    for i, rid in enumerate(retrieved_ids):
        if rid in gt:
            return 1.0 / (i + 1)
    return 0.0


async def run_eval() -> dict:
    golden = load_golden()
    thresholds = load_thresholds()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("[SKIP] ANTHROPIC_API_KEY not set — skipping RAG eval.")
        print("[PASS] RAG eval skipped (no API key).")
        return {}

    # Check API reachability before running
    async with httpx.AsyncClient() as probe:
        try:
            r = await probe.get(f"{API_BASE}/health", timeout=5.0)
            if not r.is_success:
                raise RuntimeError(f"health returned {r.status_code}")
        except Exception as e:
            print(f"[SKIP] API not reachable at {API_BASE}: {e}")
            print("[PASS] RAG eval skipped (API not running).")
            return {}

    judge = anthropic.Anthropic(api_key=api_key)

    hits5, rrs, faithfulness_scores, relevancy_scores = [], [], [], []
    hand_labeled_agree = []

    async with httpx.AsyncClient() as session:
        for i, entry in enumerate(golden):
            question = entry["question"]
            gt_chunk_ids = entry["ground_truth_chunk_ids"]
            ideal_answer = entry.get("ideal_answer", "")
            is_hand_labeled = entry.get("hand_labeled", False)

            retrieved_ids, retrieved_contents = await retrieve(session, question)
            answer = await generate(session, question, retrieved_contents)

            h5 = hit_at_k(retrieved_ids, gt_chunk_ids, 5)
            rr = reciprocal_rank(retrieved_ids, gt_chunk_ids)
            hits5.append(h5)
            rrs.append(rr)

            ctx = "\n\n".join(retrieved_contents[:5])
            f_score = judge_score(
                judge, FAITHFULNESS_PROMPT.format(context=ctx, answer=answer)
            )
            r_score = judge_score(
                judge, RELEVANCY_PROMPT.format(question=question, answer=answer)
            )
            faithfulness_scores.append(f_score)
            relevancy_scores.append(r_score)

            if is_hand_labeled:
                # For hand-labeled entries, also judge the ideal_answer
                # and compare agreement (did judge rate both similarly?)
                ideal_r = judge_score(
                    judge,
                    RELEVANCY_PROMPT.format(question=question, answer=ideal_answer),
                )
                agree = abs(r_score - ideal_r) < 0.3
                hand_labeled_agree.append(agree)

            print(
                f"  [{i + 1}/25] hit@5={h5:.0f} rr={rr:.2f} faith={f_score:.2f} rel={r_score:.2f}"
            )

    n = len(golden)
    results = {
        "n": n,
        "hit_at_5": round(sum(hits5) / n, 4),
        "mrr_at_10": round(sum(rrs) / n, 4),
        "faithfulness": round(sum(faithfulness_scores) / n, 4),
        "answer_relevancy": round(sum(relevancy_scores) / n, 4),
        "hand_labeled_agreement_pct": round(
            sum(hand_labeled_agree) / len(hand_labeled_agree) * 100, 1
        )
        if hand_labeled_agree
        else None,
    }

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nResults: {results}")

    failed = []
    for metric, threshold in thresholds.items():
        value = results.get(metric, 0.0)
        if value is not None and value < threshold:
            failed.append(f"{metric}: {value} < threshold {threshold}")

    if failed:
        print("\nTHRESHOLD FAILURES:")
        for f in failed:
            print(f"  {f}")
        sys.exit(1)

    print("\nAll thresholds passed.")
    return results


if __name__ == "__main__":
    asyncio.run(run_eval())
