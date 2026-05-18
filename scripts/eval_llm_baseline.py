"""LLM zero-shot classification baseline using Claude Haiku.

Usage:
    ANTHROPIC_API_KEY=sk-... python scripts/eval_llm_baseline.py \
        --test datasets/test_clean.csv \
        --limit 200   # set lower to control cost; use full test set for final numbers
"""

import argparse
import json
import os
import time
from pathlib import Path

import anthropic
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, f1_score

LABELS = ["bug", "feature", "docs", "question"]
OUT_DIR = Path("evals/results")

# Cost per 1M tokens for claude-haiku-4-5 (update if pricing changes)
INPUT_COST_PER_1M = 0.80
OUTPUT_COST_PER_1M = 4.00

SYSTEM_PROMPT = """You are a classifier for GitHub issues. Classify the issue into exactly one of:
- bug: something is broken or not working as expected
- feature: request for new functionality or enhancement
- docs: documentation request or correction
- question: a question about usage or behavior

Reply with exactly one word: bug, feature, docs, or question."""


def classify(client: anthropic.Anthropic, text: str) -> tuple[str, int, int, float]:
    t0 = time.perf_counter()
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text[:1500]}],
    )
    latency = (time.perf_counter() - t0) * 1000
    label = msg.content[0].text.strip().lower()
    if label not in LABELS:
        label = "bug"  # fallback for malformed responses
    return label, msg.usage.input_tokens, msg.usage.output_tokens, latency


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", required=True)
    parser.add_argument(
        "--limit", type=int, default=None, help="cap number of test examples"
    )
    args = parser.parse_args()

    df = pd.read_csv(args.test).dropna(subset=["text_clean", "label"])
    df = df[df["label"].isin(LABELS)]
    if args.limit:
        df = df.sample(min(args.limit, len(df)), random_state=42)

    print(f"evaluating {len(df)} examples with claude-haiku-4-5...")

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    preds, latencies = [], []
    total_input, total_output = 0, 0

    for i, row in df.iterrows():
        pred, n_in, n_out, lat = classify(client, row["text_clean"])
        preds.append(pred)
        latencies.append(lat)
        total_input += n_in
        total_output += n_out
        if (len(preds) % 20) == 0:
            print(f"  {len(preds)}/{len(df)}")

    y_true = df["label"].tolist()
    accuracy = accuracy_score(y_true, preds)
    macro_f1 = f1_score(y_true, preds, average="macro", labels=LABELS, zero_division=0)
    report = classification_report(
        y_true, preds, target_names=LABELS, output_dict=True, zero_division=0
    )

    cost = (total_input / 1_000_000 * INPUT_COST_PER_1M) + (
        total_output / 1_000_000 * OUTPUT_COST_PER_1M
    )
    cost_per_1k = cost / len(df) * 1000

    import numpy as np

    latency_p50 = float(np.percentile(latencies, 50))

    print(f"\naccuracy: {accuracy:.4f}  macro-F1: {macro_f1:.4f}")
    print(f"latency p50: {latency_p50:.0f}ms  cost/1k: ${cost_per_1k:.4f}")
    print(classification_report(y_true, preds, target_names=LABELS, zero_division=0))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result = {
        "model": "claude-haiku-4-5-20251001",
        "n_examples": len(df),
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "per_class_f1": {lbl: round(report[lbl]["f1-score"], 4) for lbl in LABELS},
        "latency_p50_ms": round(latency_p50, 1),
        "cost_per_1k_usd": round(cost_per_1k, 4),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
    }
    (OUT_DIR / "llm_baseline_results.json").write_text(json.dumps(result, indent=2))
    print(f"saved to {OUT_DIR}/llm_baseline_results.json")


if __name__ == "__main__":
    main()
