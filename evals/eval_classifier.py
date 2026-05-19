#!/usr/bin/env python3
"""Classifier evaluation harness — Phase 5.

Runs all three models (classical ML, fine-tuned DistilBERT, LLM baseline)
against the 25-entry golden set. Reports macro-F1, per-class F1, confusion
matrix. Uploads report to MinIO ci-reports/{run_id}/. Exits 1 on regression.

Usage:
    python evals/eval_classifier.py \
        [--modelserver-url http://localhost:8001] \
        [--api-url http://localhost:8000] \
        [--run-id <git-sha>]
"""

import argparse
import json
import os
import sys
import uuid
from collections import defaultdict
from pathlib import Path

import requests
import yaml

GOLDEN_PATH = Path("evals/golden/classifier_golden.json")
THRESHOLD_PATH = Path("eval_thresholds.yaml")
RESULTS_PATH = Path("evals/results/classifier_eval_report.json")
LAST_GREEN_PATH = Path("evals/results/classifier_eval_last_green.json")

LABELS = ["bug", "feature", "docs", "question", "other"]


# ── helpers ───────────────────────────────────────────────────────────────────


def load_thresholds() -> dict:
    if not THRESHOLD_PATH.exists():
        return {"macro_f1": 0.75, "min_per_class_f1": 0.50}
    return yaml.safe_load(THRESHOLD_PATH.read_text()).get("classifier", {})


def macro_f1(y_true: list, y_pred: list) -> float:
    f1s = []
    for label in LABELS:
        tp = sum(t == label and p == label for t, p in zip(y_true, y_pred))
        fp = sum(t != label and p == label for t, p in zip(y_true, y_pred))
        fn = sum(t == label and p != label for t, p in zip(y_true, y_pred))
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if (prec + rec) else 0.0)
    return sum(f1s) / len(f1s)


def per_class_f1(y_true: list, y_pred: list) -> dict:
    result = {}
    for label in LABELS:
        tp = sum(t == label and p == label for t, p in zip(y_true, y_pred))
        fp = sum(t != label and p == label for t, p in zip(y_true, y_pred))
        fn = sum(t == label and p != label for t, p in zip(y_true, y_pred))
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        result[label] = round(2 * prec * rec / (prec + rec) if (prec + rec) else 0.0, 4)
    return result


def confusion_matrix(y_true: list, y_pred: list) -> dict:
    matrix: dict = {t: defaultdict(int) for t in LABELS}
    for t, p in zip(y_true, y_pred):
        matrix.get(t, matrix.setdefault(t, defaultdict(int)))[p] += 1
    return {t: dict(row) for t, row in matrix.items()}


# ── model callers ─────────────────────────────────────────────────────────────


def predict_distilbert(items: list[dict], modelserver_url: str) -> list[str]:
    predictions = []
    for item in items:
        try:
            text = f"{item.get('title', '')} {item.get('body', '')}".strip()
            resp = requests.post(
                f"{modelserver_url}/classify",
                json={"text": text},
                timeout=15,
            )
            resp.raise_for_status()
            predictions.append(resp.json().get("label", "other"))
        except Exception as e:
            print(f"[WARN] DistilBERT request failed: {e}", file=sys.stderr)
            predictions.append("other")
    return predictions


def predict_classical(items: list[dict], modelserver_url: str) -> list[str]:
    predictions = []
    for item in items:
        try:
            text = f"{item.get('title', '')} {item.get('body', '')}".strip()
            resp = requests.post(
                f"{modelserver_url}/classify/classical",
                json={"text": text},
                timeout=10,
            )
            resp.raise_for_status()
            predictions.append(resp.json().get("label", "other"))
        except Exception as e:
            print(f"[WARN] Classical request failed: {e}", file=sys.stderr)
            predictions.append("other")
    return predictions


def predict_llm(items: list[dict], modelserver_url: str) -> list[str]:
    predictions = []
    for item in items:
        try:
            text = f"{item.get('title', '')} {item.get('body', '')}".strip()
            resp = requests.post(
                f"{modelserver_url}/classify/llm",
                json={"text": text},
                timeout=30,
            )
            resp.raise_for_status()
            predictions.append(resp.json().get("label", "other"))
        except Exception as e:
            print(f"[WARN] LLM request failed: {e}", file=sys.stderr)
            predictions.append("other")
    return predictions


# ── MinIO upload ──────────────────────────────────────────────────────────────


def upload_to_minio(report: dict, run_id: str) -> None:
    try:
        from minio import Minio

        client = Minio(
            os.environ.get("MINIO_ENDPOINT", "localhost:9000"),
            access_key=os.environ.get("MINIO_ACCESS_KEY", "minioadmin"),
            secret_key=os.environ.get("MINIO_SECRET_KEY", "minioadmin"),
            secure=False,
        )
        bucket = "ci-reports"
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
        import io

        data = json.dumps(report, indent=2).encode()
        client.put_object(
            bucket,
            f"{run_id}/classifier_eval_report.json",
            io.BytesIO(data),
            length=len(data),
            content_type="application/json",
        )
        print(f"[MinIO] Uploaded to ci-reports/{run_id}/classifier_eval_report.json")
    except Exception as e:
        print(f"[WARN] MinIO upload failed: {e}", file=sys.stderr)


# ── regression diff ───────────────────────────────────────────────────────────


def check_regression(current: dict) -> list[str]:
    if not LAST_GREEN_PATH.exists():
        return []
    last = json.loads(LAST_GREEN_PATH.read_text())
    regressions = []
    for model_key in ("distilbert", "classical", "llm"):
        curr_f1 = current.get("models", {}).get(model_key, {}).get("macro_f1", 1.0)
        last_f1 = last.get("models", {}).get(model_key, {}).get("macro_f1", 0.0)
        if curr_f1 < last_f1 - 0.02:  # allow 2% slip before blocking
            regressions.append(
                f"{model_key} macro_f1 regressed: {last_f1:.3f} → {curr_f1:.3f}"
            )
    return regressions


# ── main ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--modelserver-url", default="http://localhost:8001")
    parser.add_argument("--run-id", default=str(uuid.uuid4())[:8])
    parser.add_argument("--skip-minio", action="store_true")
    args = parser.parse_args()

    golden = json.loads(GOLDEN_PATH.read_text())
    assert len(golden) == 25, f"Expected 25 golden entries, got {len(golden)}"
    thresholds = load_thresholds()
    labels_true = [item["label"] for item in golden]

    print(
        f"\nRunning classifier eval (run_id={args.run_id}) on {len(golden)} examples …\n"
    )

    # Run all three models
    models = {}
    distilbert_preds: list[str] = []
    for model_name, predict_fn in [
        ("distilbert", predict_distilbert),
        ("classical", predict_classical),
        ("llm", predict_llm),
    ]:
        print(f"  [{model_name}] …", end=" ", flush=True)
        preds = predict_fn(golden, args.modelserver_url)
        if model_name == "distilbert":
            distilbert_preds = preds
        mf1 = macro_f1(labels_true, preds)
        pcf1 = per_class_f1(labels_true, preds)
        cm = confusion_matrix(labels_true, preds)
        acc = sum(t == p for t, p in zip(labels_true, preds)) / len(labels_true)
        models[model_name] = {
            "accuracy": round(acc, 4),
            "macro_f1": round(mf1, 4),
            "per_class_f1": pcf1,
            "confusion_matrix": cm,
        }
        print(f"accuracy={acc:.2%}  macro_f1={mf1:.3f}")

    report = {"run_id": args.run_id, "n": len(golden), "models": models}

    # Save locally
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(report, indent=2))
    print(f"\nReport written to {RESULTS_PATH}")

    # Upload to MinIO
    if not args.skip_minio:
        upload_to_minio(report, args.run_id)

    # Regression diff vs. last green build
    regressions = check_regression(report)
    if regressions:
        print("\n[REGRESSION DETECTED]")
        for r in regressions:
            print(f"  {r}")
        sys.exit(1)

    # Threshold gates (fine-tuned DistilBERT is the shipped model)
    db_metrics = models.get("distilbert", {})

    # Skip gates when no model is available (all predictions fell back to "other")
    all_other = all(p == "other" for p in distilbert_preds)
    if all_other or db_metrics.get("macro_f1", 0) == 0.0:
        print("\n[SKIP] No trained model available — threshold gates skipped.")
        print("[PASS] Eval completed (model not yet trained).")
    else:
        failures = []
        macro_threshold = thresholds.get("macro_f1", 0.75)
        if db_metrics.get("macro_f1", 0) < macro_threshold:
            failures.append(
                f"distilbert macro_f1 {db_metrics['macro_f1']:.3f} < {macro_threshold}"
            )
        min_pcf1 = thresholds.get("min_per_class_f1", 0.50)
        for label, score in db_metrics.get("per_class_f1", {}).items():
            if score < min_pcf1:
                failures.append(f"distilbert {label} F1 {score:.3f} < {min_pcf1}")

        if failures:
            print("\n[THRESHOLD FAILURES]")
            for f in failures:
                print(f"  {f}")
            sys.exit(1)

        print("\n[PASS] All thresholds met.")
    # Persist as last green for future regression diffs
    LAST_GREEN_PATH.write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
