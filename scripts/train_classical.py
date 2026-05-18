"""Classical ML baseline: TF-IDF + Logistic Regression.

Usage:
    python scripts/train_classical.py \
        --train datasets/train_clean.csv \
        --val   datasets/val_clean.csv \
        --test  datasets/test_clean.csv
"""

import argparse
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.pipeline import Pipeline

LABELS = ["bug", "feature", "docs", "question"]
OUT_DIR = Path("evals/results")
MODEL_PATH = Path("models/classical_pipeline.joblib")


def load(path: str) -> tuple[list[str], list[str]]:
    df = pd.read_csv(path).dropna(subset=["text_clean", "label"])
    df = df[df["label"].isin(LABELS)]
    return df["text_clean"].tolist(), df["label"].tolist()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", required=True)
    parser.add_argument("--val", required=True)
    parser.add_argument("--test", required=True)
    args = parser.parse_args()

    X_train, y_train = load(args.train)
    X_val, y_val = load(args.val)
    X_test, y_test = load(args.test)

    # Combine train+val for final fit (we already tuned nothing, so it's fine)
    X_fit = X_train + X_val
    y_fit = y_train + y_val

    pipeline = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    max_features=50_000, ngram_range=(1, 2), sublinear_tf=True
                ),
            ),
            ("clf", LogisticRegression(C=1.0, max_iter=1000, class_weight="balanced")),
        ]
    )

    pipeline.fit(X_fit, y_fit)

    y_pred = pipeline.predict(X_test)

    # Measure p50 latency on single samples
    times = []
    for text in X_test[:200]:
        t0 = time.perf_counter()
        pipeline.predict([text])
        times.append((time.perf_counter() - t0) * 1000)
    latency_p50 = float(np.percentile(times, 50))

    report = classification_report(
        y_test, y_pred, target_names=LABELS, output_dict=True
    )
    accuracy = accuracy_score(y_test, y_pred)
    macro_f1 = f1_score(y_test, y_pred, average="macro")

    print(
        f"accuracy: {accuracy:.4f}  macro-F1: {macro_f1:.4f}  latency p50: {latency_p50:.2f}ms"
    )
    print(classification_report(y_test, y_pred, target_names=LABELS))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result = {
        "model": "TF-IDF + LogisticRegression",
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "per_class_f1": {lbl: round(report[lbl]["f1-score"], 4) for lbl in LABELS},
        "latency_p50_ms": round(latency_p50, 2),
        "cost_per_1k": 0.0,
        "notes": "TF-IDF max_features=50k, ngram(1,2), sublinear_tf; LR C=1.0 balanced",
    }
    (OUT_DIR / "classical_results.json").write_text(json.dumps(result, indent=2))
    print(f"results saved to {OUT_DIR}/classical_results.json")

    # Save pipeline for modelserver
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    print(f"pipeline saved to {MODEL_PATH}")

    # Upload to MinIO
    try:
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent))
        from app.infra import vault, minio_client

        vault.load_secrets()
        minio_client.init()
        with open(MODEL_PATH, "rb") as f:
            data = f.read()
        minio_client.put_bytes(
            "models", "classical/pipeline.joblib", data, "application/octet-stream"
        )
        print("uploaded to MinIO models/classical/pipeline.joblib")
    except Exception as e:
        print(f"[WARN] MinIO upload skipped: {e}")


if __name__ == "__main__":
    main()
