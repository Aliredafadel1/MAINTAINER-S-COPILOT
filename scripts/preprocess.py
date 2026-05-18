"""Clean and normalize issue text for classifier training and RAG ingestion.

Usage:
    python scripts/preprocess.py --input datasets/train.csv --output datasets/train_clean.csv
    python scripts/preprocess.py --input datasets/val.csv   --output datasets/val_clean.csv
    python scripts/preprocess.py --input datasets/test.csv  --output datasets/test_clean.csv
"""

import argparse
import re
from pathlib import Path

import pandas as pd

MAX_CHARS = 2000  # ~512 DistilBERT tokens with headroom


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def strip_code_fences(text: str) -> str:
    # Remove ```...``` blocks — they add noise without semantic signal for classification
    return re.sub(r"```[\s\S]*?```", " [CODE] ", text)


def strip_inline_code(text: str) -> str:
    return re.sub(r"`[^`]+`", " [CODE] ", text)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def strip_urls(text: str) -> str:
    return re.sub(r"https?://\S+", " [URL] ", text)


def clean(text: str) -> str:
    text = strip_html(text)
    text = strip_code_fences(text)
    text = strip_inline_code(text)
    text = strip_urls(text)
    text = normalize_whitespace(text)
    return text[:MAX_CHARS]


def process(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["title_clean"] = df["title"].fillna("").apply(clean)
    df["body_clean"] = df["body"].fillna("").apply(clean)
    # Combine title + body; title gets extra weight by repeating it
    df["text_clean"] = (
        df["title_clean"] + " " + df["title_clean"] + " " + df["body_clean"]
    )
    df["text_clean"] = df["text_clean"].apply(normalize_whitespace).str[:MAX_CHARS]
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    df = process(df)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"processed {len(df)} rows → {args.output}")
    print(f"avg text length: {df['text_clean'].str.len().mean():.0f} chars")


if __name__ == "__main__":
    main()
