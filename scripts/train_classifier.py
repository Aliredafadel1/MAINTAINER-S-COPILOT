"""Fine-tune DistilBERT for 4-class issue classification.

Usage:
    MINIO_ENDPOINT=localhost:9000 \
    MINIO_ACCESS_KEY=minioadmin \
    MINIO_SECRET_KEY=minioadmin \
    MLFLOW_TRACKING_URI=./mlruns \
    python scripts/train_classifier.py \
        --train datasets/train_clean.csv \
        --val   datasets/val_clean.csv \
        --test  datasets/test_clean.csv
"""

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
import torch
from minio import Minio
from sklearn.metrics import accuracy_score, classification_report, f1_score
from transformers import (
    DistilBertForSequenceClassification,
    DistilBertTokenizerFast,
    Trainer,
    TrainingArguments,
    EarlyStoppingCallback,
)
from datasets import Dataset

LABELS = ["bug", "feature", "docs", "question"]
LABEL2ID = {lbl: i for i, lbl in enumerate(LABELS)}
ID2LABEL = {i: lbl for i, lbl in enumerate(LABELS)}

MODEL_NAME = "distilbert-base-uncased"
MAX_LEN = 512
OUTPUT_DIR = Path("model_output/classifier")
MINIO_BUCKET = "models"
MINIO_PREFIX = "classifier"


def load_split(path: str) -> Dataset:
    df = pd.read_csv(path)
    df = df.dropna(subset=["text_clean", "label"])
    df = df[df["label"].isin(LABELS)]
    df["labels"] = df["label"].map(LABEL2ID)
    return Dataset.from_pandas(
        df[["text_clean", "labels"]].rename(columns={"text_clean": "text"})
    )


def tokenize(batch, tokenizer):
    return tokenizer(
        batch["text"], truncation=True, max_length=MAX_LEN, padding="max_length"
    )


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "macro_f1": f1_score(labels, preds, average="macro"),
    }


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def upload_to_minio(local_dir: Path, bucket: str, prefix: str) -> None:
    client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=False,
    )
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    for f in local_dir.rglob("*"):
        if f.is_file():
            key = f"{prefix}/{f.relative_to(local_dir)}"
            client.fput_object(bucket, key, str(f))
            print(f"  uploaded {key}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", required=True)
    parser.add_argument("--val", required=True)
    parser.add_argument("--test", required=True)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=3e-5)
    args = parser.parse_args()

    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "./mlruns"))
    mlflow.set_experiment("issue-classifier")

    tokenizer = DistilBertTokenizerFast.from_pretrained(MODEL_NAME)

    train_ds = load_split(args.train).map(
        lambda b: tokenize(b, tokenizer), batched=True
    )
    val_ds = load_split(args.val).map(lambda b: tokenize(b, tokenizer), batched=True)
    test_ds = load_split(args.test).map(lambda b: tokenize(b, tokenizer), batched=True)

    train_ds.set_format("torch", columns=["input_ids", "attention_mask", "labels"])
    val_ds.set_format("torch", columns=["input_ids", "attention_mask", "labels"])
    test_ds.set_format("torch", columns=["input_ids", "attention_mask", "labels"])

    model = DistilBertForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=len(LABELS),
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )

    # Freeze all transformer layers except the last block and classifier head.
    # Rationale: the first 4 blocks learn general language; only the last block
    # and head need to adapt to the domain-specific label space.
    for name, param in model.distilbert.named_parameters():
        if not name.startswith("transformer.layer.5"):
            param.requires_grad = False

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(
        f"trainable params: {trainable:,} / {total:,} ({100 * trainable / total:.1f}%)"
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=32,
        learning_rate=args.lr,
        warmup_ratio=0.1,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        report_to="mlflow",
        logging_steps=50,
        fp16=torch.cuda.is_available(),
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
    )

    with mlflow.start_run() as run:
        mlflow.log_params(
            {
                "base_model": MODEL_NAME,
                "epochs": args.epochs,
                "batch_size": args.batch_size,
                "lr": args.lr,
                "freeze_policy": "all_except_layer5_and_head",
                "max_len": MAX_LEN,
            }
        )

        trainer.train()

        # Evaluate on test set
        test_preds = trainer.predict(test_ds)
        y_pred = np.argmax(test_preds.predictions, axis=-1)
        y_true = test_preds.label_ids

        t0 = time.perf_counter()
        for _ in range(100):
            trainer.predict(test_ds.select(range(1)))
        latency_ms = (time.perf_counter() - t0) / 100 * 1000

        report = classification_report(
            y_true, y_pred, target_names=LABELS, output_dict=True
        )
        macro_f1 = report["macro avg"]["f1-score"]
        accuracy = report["accuracy"]

        mlflow.log_metrics(
            {
                "test_accuracy": accuracy,
                "test_macro_f1": macro_f1,
                "latency_p50_ms": latency_ms,
                **{f"test_f1_{lbl}": report[lbl]["f1-score"] for lbl in LABELS},
            }
        )

        print(f"\nTest accuracy: {accuracy:.4f}  macro-F1: {macro_f1:.4f}")
        print(classification_report(y_true, y_pred, target_names=LABELS))

        # Save tokenizer alongside model
        tokenizer.save_pretrained(str(OUTPUT_DIR))

        weights_sha = sha256_file(OUTPUT_DIR / "model.safetensors")

        # Load train CSV sha from dataset_meta.json if present
        meta_path = Path(args.train).parent / "dataset_meta.json"
        train_sha = (
            json.loads(meta_path.read_text())["train_sha256"]
            if meta_path.exists()
            else ""
        )

        model_card = {
            "architecture": MODEL_NAME,
            "task": "sequence-classification",
            "labels": LABELS,
            "hyperparameters": {
                "epochs": args.epochs,
                "batch_size": args.batch_size,
                "learning_rate": args.lr,
                "max_length": MAX_LEN,
                "freeze_policy": "all_except_layer5_and_head",
            },
            "training_data_sha256": train_sha,
            "weights_sha256": weights_sha,
            "metrics": {
                "accuracy": round(accuracy, 4),
                "macro_f1": round(macro_f1, 4),
                **{f"f1_{lbl}": round(report[lbl]["f1-score"], 4) for lbl in LABELS},
                "latency_p50_ms": round(latency_ms, 2),
            },
            "mlflow_run_id": run.info.run_id,
        }
        card_path = OUTPUT_DIR / "model_card.json"
        card_path.write_text(json.dumps(model_card, indent=2))
        mlflow.log_artifact(str(card_path))

        print(f"\nweights SHA-256: {weights_sha}")
        print(f"uploading to MinIO {MINIO_BUCKET}/{MINIO_PREFIX}...")
        upload_to_minio(OUTPUT_DIR, MINIO_BUCKET, MINIO_PREFIX)
        print("done")


if __name__ == "__main__":
    main()
