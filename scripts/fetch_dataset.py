"""Fetch closed issues from a GitHub repo and produce stratified train/val/test splits.

Usage:
    GITHUB_TOKEN=... python scripts/fetch_dataset.py --repo owner/repo --out datasets/
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import pandas as pd
import requests
from sklearn.model_selection import train_test_split

# Map repo labels -> canonical class. Edit this mapping after choosing your repo.
# Document the final mapping in DECISIONS.md.
LABEL_MAP: dict[str, str] = {
    "bug": "bug",
    "type: bug": "bug",
    "kind/bug": "bug",
    "feature": "feature",
    "enhancement": "feature",
    "type: feature": "feature",
    "kind/feature": "feature",
    "documentation": "docs",
    "docs": "docs",
    "type: docs": "docs",
    "question": "question",
    "help wanted": "question",
    "type: question": "question",
}

CLASSES = ["bug", "feature", "docs", "question"]


def fetch_issues(repo: str, token: str, max_pages: int = 30) -> list[dict]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    issues = []
    for page in range(1, max_pages + 1):
        resp = requests.get(
            f"https://api.github.com/repos/{repo}/issues",
            headers=headers,
            params={"state": "closed", "per_page": 100, "page": page},
            timeout=30,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        # Skip pull requests (GitHub returns them mixed with issues)
        issues.extend(i for i in batch if "pull_request" not in i)
        print(f"  page {page}: {len(batch)} items, {len(issues)} issues so far")
    return issues


def map_label(labels: list[dict]) -> str | None:
    for lbl in labels:
        canonical = LABEL_MAP.get(lbl["name"].lower())
        if canonical:
            return canonical
    return None


def build_dataframe(issues: list[dict]) -> pd.DataFrame:
    rows = []
    for issue in issues:
        label = map_label(issue.get("labels", []))
        if label is None:
            continue
        rows.append(
            {
                "id": issue["number"],
                "title": issue.get("title", ""),
                "body": issue.get("body") or "",
                "label": label,
                "created_at": issue["created_at"],
            }
        )
    df = pd.DataFrame(rows)
    df["text"] = df["title"] + " " + df["body"]
    df = df.drop_duplicates(subset=["id"])
    df = df.sort_values("created_at").reset_index(drop=True)
    return df


def split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    # Test set = most recent 15% of time-ordered data (strictly newer than train)
    cutoff = int(len(df) * 0.85)
    train_val = df.iloc[:cutoff]
    test = df.iloc[cutoff:]

    train, val = train_test_split(
        train_val, test_size=0.15, stratify=train_val["label"], random_state=42
    )
    return (
        train.reset_index(drop=True),
        val.reset_index(drop=True),
        test.reset_index(drop=True),
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="owner/repo")
    parser.add_argument("--out", default="datasets", help="output directory")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("GITHUB_TOKEN env var required", file=sys.stderr)
        sys.exit(1)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print(f"fetching closed issues from {args.repo}...")
    issues = fetch_issues(args.repo, token)
    print(f"total issues fetched: {len(issues)}")

    raw_path = out / "raw_issues.json"
    raw_path.write_text(json.dumps(issues, indent=2))

    df = build_dataframe(issues)
    print(f"labeled issues: {len(df)}")
    print(df["label"].value_counts().to_string())

    train, val, test = split(df)
    print(f"splits — train: {len(train)}, val: {len(val)}, test: {len(test)}")

    train.to_csv(out / "train.csv", index=False)
    val.to_csv(out / "val.csv", index=False)
    test.to_csv(out / "test.csv", index=False)

    train_hash = sha256(out / "train.csv")
    meta = {
        "repo": args.repo,
        "total_labeled": len(df),
        "train": len(train),
        "val": len(val),
        "test": len(test),
        "class_distribution": df["label"].value_counts().to_dict(),
        "train_sha256": train_hash,
    }
    (out / "dataset_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"train SHA-256: {train_hash}")
    print("done")


if __name__ == "__main__":
    main()
