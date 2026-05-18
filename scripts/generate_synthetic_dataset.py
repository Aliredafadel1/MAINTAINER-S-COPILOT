"""Generate synthetic GitHub issues dataset for EDA notebook development.

Produces datasets/raw_issues.json and all train/val/test CSV splits.
Run once: python scripts/generate_synthetic_dataset.py
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

random.seed(42)

LABELS = ["bug", "feature", "docs", "question"]

# Realistic issue templates per class
TEMPLATES = {
    "bug": [
        (
            "TypeError when calling {func} with {type} argument",
            "I'm using version {ver}. When I call `{func}({arg})` I get:\n```\nTypeError: expected {type}, got {other}\n```\nThis worked in v{oldver}. Steps to reproduce:\n1. Install `pip install lib=={ver}`\n2. Run the attached script\n\nOS: {os}, Python: {pyver}",
        ),
        (
            "ConnectionError after {n} retries with async client",
            "Using {lib} {ver} on Python {pyver}.\nWhen the server is slow, I get `ConnectionError` after exactly {n} retries even though I set `TIMEOUT={t}`.\n\nTraceback:\n```\nConnectionError: max retries exceeded\n  File 'client.py', line {line}\n```",
        ),
        (
            "{func} raises AttributeError on {os}",
            "Reproduction:\n```python\nfrom lib import {cls}\nobj = {cls}()\nobj.{func}()  # AttributeError: '{cls}' has no attribute '{attr}'\n```\nWorks fine on macOS, fails on {os}. Version {ver}.",
        ),
        (
            "Memory leak in {cls} when processing large files",
            "I notice memory usage grows unboundedly when using `{cls}` to process files > {size}MB.\n\nProfile output:\n```\n{cls}.process(): 2.3GB allocated, not released\n```\nUsing {lib} {ver}, {os}.",
        ),
        (
            "Race condition in {func} under concurrent load",
            "Under concurrent requests ({n} workers), `{func}` occasionally returns stale data or raises `RuntimeError: dictionary changed size`.\n\nReproduction script:\n```python\nimport threading\nthreads = [threading.Thread(target={func}) for _ in range({n})]\n```\nVersion: {ver}",
        ),
        (
            "ValueError when {func} receives empty input",
            "`{func}([])` raises `ValueError: list is empty` instead of returning an empty result.\n\nExpected: return `[]`\nActual: raises exception\n\nVersion {ver}, Python {pyver}",
        ),
    ],
    "feature": [
        (
            "Add support for {fmt} export format",
            "It would be great to export results in `{fmt}` format in addition to the existing options.\n\nUse case: I'm integrating with {tool} which only accepts {fmt}.\n\nI'm happy to contribute a PR if the maintainers agree this is worth adding.",
        ),
        (
            "Support async context manager in {cls}",
            "Currently `{cls}` only supports synchronous context managers (`with` statement).\n\nIt would be very useful to support `async with {cls}() as ctx:` for use in asyncio applications.\n\nRelated: #{n}",
        ),
        (
            "Add {metric} to metrics output",
            "The current metrics output includes accuracy and F1 but not {metric}.\n\n{metric} is important for our use case because {reason}.\n\nWould it be possible to add it as an optional output field?",
        ),
        (
            "Configurable {param} per request",
            "Currently `{param}` is set globally at initialization time. It would be helpful to override it per-request.\n\nProposed API:\n```python\nclient.call(data, {param}={value})\n```",
        ),
        (
            "Add CLI command for {action}",
            "There's no CLI command to {action}. Users currently have to write a Python script.\n\nProposed:\n```bash\nlib {action} --input file.json --output out/\n```\n\nThis would significantly improve the DX for non-Python users.",
        ),
        (
            "Plugin system for custom {component}",
            "Would love to see a plugin system so third-party packages can register custom `{component}` implementations.\n\nSomething like:\n```python\n@lib.register_plugin('{component}')\nclass My{cls}({base}):\n    ...\n```",
        ),
    ],
    "docs": [
        (
            "Documentation for {func} is missing return type",
            'The docstring for `{func}` doesn\'t mention what it returns. Looking at the source it returns `{type}` but this should be documented.\n\nCurrently:\n```\ndef {func}(x):\n    """Process x."""\n```\n\nExpected:\n```\ndef {func}(x) -> {type}:\n    """Process x.\n    Returns: {type} — ...\n    """\n```',
        ),
        (
            "Getting started guide is outdated — still references v{oldver} API",
            "The Getting Started guide at docs/quickstart.md still shows the v{oldver} API:\n```python\nfrom lib import OldClient  # removed in v{ver}\n```\nThe new API is:\n```python\nfrom lib import Client\n```\nCould the docs be updated?",
        ),
        (
            "Add example for {usecase} to cookbook",
            "The cookbook covers basic usage but doesn't have an example for {usecase}.\n\nThis is a common pattern and I had to figure it out by reading the source. A short example would save others the same time.",
        ),
        (
            "Broken link in {page} page",
            "The link to `{target}` on the {page} page returns 404.\n\nLink: https://docs.example.com/{path}\n\nIt seems like the page was moved or renamed.",
        ),
        (
            "README installation instructions don't work on {os}",
            "Following the README installation steps on {os} fails at:\n```\npip install lib[extra]\nerror: Microsoft Visual C++ 14.0 required\n```\n\nThe README should document the {os}-specific prerequisites.",
        ),
    ],
    "question": [
        (
            "How to use {cls} with {framework}?",
            "I'm trying to integrate `{cls}` with `{framework}` but I'm not sure how to configure it correctly.\n\nMy current code:\n```python\nfrom lib import {cls}\nfrom {framework} import App\n\napp = App()\n# How do I attach {cls} here?\n```\n\nAny examples or pointers would be helpful!",
        ),
        (
            "What is the recommended way to handle {scenario}?",
            "I have a use case where I need to {scenario}. I see a few possible approaches:\n\n1. Use `{opt1}` — but I'm not sure if it's thread-safe\n2. Use `{opt2}` — seems more heavyweight\n\nWhat is the recommended approach? Is there documentation I missed?",
        ),
        (
            "Is {feature} planned for a future release?",
            "I need {feature} for my project. I searched the issues and didn't find any existing discussion.\n\nIs this something the maintainers are considering? If not, I might try to submit a PR.",
        ),
        (
            "Performance of {func} with large datasets",
            "I'm using `{func}` on datasets with ~{n}M rows and it's quite slow (~{t}s per batch).\n\nIs this expected? Are there any tips for improving performance — batching, parallelism, different parameters?",
        ),
        (
            "How does {cls} handle {edge_case}?",
            "I couldn't find documentation on how `{cls}` behaves when {edge_case}.\n\nFor example:\n```python\nresult = {cls}().process(None)  # what happens?\n```\n\nDoes it raise, return None, or something else?",
        ),
    ],
}

FILL = {
    "func": [
        "process",
        "encode",
        "fit",
        "transform",
        "predict",
        "load",
        "save",
        "parse",
        "validate",
        "run",
    ],
    "cls": [
        "Client",
        "Model",
        "Pipeline",
        "Encoder",
        "Processor",
        "Loader",
        "Cache",
        "Session",
    ],
    "type": ["str", "list", "dict", "int", "bytes", "tensor", "DataFrame"],
    "other": ["NoneType", "float", "tuple", "set"],
    "lib": [
        "transformers",
        "torch",
        "fastapi",
        "pydantic",
        "httpx",
        "sqlalchemy",
        "pandas",
    ],
    "ver": ["4.35.0", "2.1.0", "0.110.0", "1.9.0", "3.0.1", "2.0.3", "0.8.1"],
    "oldver": ["4.30.0", "2.0.0", "0.109.0", "1.8.0", "2.9.0"],
    "pyver": ["3.10", "3.11", "3.12"],
    "os": ["Windows 11", "Ubuntu 22.04", "macOS 14"],
    "n": ["3", "10", "50", "100", "1000"],
    "t": ["30", "60", "120"],
    "line": ["142", "87", "321", "56"],
    "size": ["100", "500", "1000"],
    "attr": ["close", "reset", "flush", "read"],
    "arg": ["None", "[]", '""', "0"],
    "fmt": ["CSV", "Parquet", "Arrow", "JSON Lines", "HDF5"],
    "tool": ["dbt", "Spark", "Airflow", "Kafka", "Grafana"],
    "metric": ["precision@k", "NDCG", "MRR", "latency_p99", "token_count"],
    "reason": ["imbalanced datasets", "our SLA requirements", "regulatory compliance"],
    "param": ["timeout", "batch_size", "max_retries", "temperature", "chunk_size"],
    "value": ["60", "128", "5", "0.7", "512"],
    "action": ["export", "validate", "migrate", "benchmark", "lint"],
    "component": ["tokenizer", "classifier", "retriever", "encoder", "cache"],
    "base": ["BaseTokenizer", "BaseClassifier", "BaseRetriever"],
    "usecase": [
        "streaming large files",
        "batch inference",
        "multi-GPU training",
        "hot-reloading models",
    ],
    "page": ["API reference", "migration guide", "configuration", "installation"],
    "target": ["changelog", "contributing guide", "examples notebook"],
    "path": ["docs/changelog", "guides/contributing", "examples/notebook"],
    "framework": ["FastAPI", "Django", "Flask", "Starlette", "Celery"],
    "scenario": [
        "handle connection pooling",
        "cache model weights",
        "retry on timeout",
        "stream large responses",
    ],
    "opt1": ["connection_pool", "async_client", "cached_model"],
    "opt2": ["new Client() per request", "thread-local storage", "multiprocessing"],
    "feature": ["batch export", "async support", "plugin hooks", "streaming API"],
    "edge_case": [
        "input is None",
        "the list is empty",
        "the key doesn't exist",
        "the file is locked",
    ],
}


def fill(template: str) -> str:
    import re

    keys = re.findall(r"\{(\w+)\}", template)
    replacements = {}
    for k in keys:
        if k in FILL:
            replacements[k] = random.choice(FILL[k])
        else:
            replacements[k] = k
    return template.format_map(replacements)


def make_issue(number: int, label: str, created_at: datetime) -> dict:
    title_tmpl, body_tmpl = random.choice(TEMPLATES[label])
    title = fill(title_tmpl)
    body = fill(body_tmpl)
    # Map label to a GitHub-style label name
    gh_label_names = {
        "bug": random.choice(["bug", "type: bug", "kind/bug"]),
        "feature": random.choice(["enhancement", "feature", "type: feature"]),
        "docs": random.choice(["documentation", "docs"]),
        "question": random.choice(["question", "help wanted"]),
    }
    return {
        "number": number,
        "title": title,
        "body": body,
        "labels": [{"name": gh_label_names[label]}],
        "created_at": created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "state": "closed",
    }


def main() -> None:
    out = Path("datasets")
    out.mkdir(exist_ok=True)

    # Class proportions: bug 35%, feature 30%, docs 15%, question 20%
    class_counts = {"bug": 105, "feature": 90, "docs": 45, "question": 60}
    total = sum(class_counts.values())  # 300

    # Generate issues spanning 2022-01-01 to 2024-12-31 (ordered chronologically)
    start = datetime(2022, 1, 1)
    end = datetime(2024, 12, 31)
    span_days = (end - start).days

    issues = []
    number = 1
    label_pool = []
    for label, count in class_counts.items():
        label_pool.extend([label] * count)
    random.shuffle(label_pool)

    # Assign timestamps in roughly increasing order
    timestamps = sorted(
        start + timedelta(days=random.uniform(0, span_days)) for _ in range(total)
    )

    for i, (label, ts) in enumerate(zip(label_pool, timestamps)):
        # Occasionally add issues with no body (~8%)
        if random.random() < 0.08:
            issue = make_issue(number + i, label, ts)
            issue["body"] = None
        else:
            issue = make_issue(number + i, label, ts)
        issues.append(issue)

    # Add some multi-label issues (5%) that get filtered to single canonical label
    extra = []
    for i in range(15):
        ts = start + timedelta(days=random.uniform(0, span_days))
        label = random.choice(LABELS)
        issue = make_issue(number + total + i, label, ts)
        # Add a second mappable label
        second = random.choice([lbl for lbl in LABELS if lbl != label])
        gh_map2 = {
            "bug": "type: bug",
            "feature": "enhancement",
            "docs": "documentation",
            "question": "help wanted",
        }
        issue["labels"].append({"name": gh_map2[second]})
        extra.append(issue)
    issues.extend(extra)

    # Sort all by created_at for realistic ordering
    issues.sort(key=lambda x: x["created_at"])

    (out / "raw_issues.json").write_text(json.dumps(issues, indent=2))
    print(f"wrote {len(issues)} raw issues")

    # Build dataframe (same logic as fetch_dataset.py)
    LABEL_MAP = {
        "bug": "bug",
        "type: bug": "bug",
        "kind/bug": "bug",
        "feature": "feature",
        "enhancement": "feature",
        "type: feature": "feature",
        "documentation": "docs",
        "docs": "docs",
        "question": "question",
        "help wanted": "question",
    }

    rows = []
    for issue in issues:
        label = None
        for lbl in issue.get("labels", []):
            canonical = LABEL_MAP.get(lbl["name"].lower())
            if canonical:
                label = canonical
                break
        if label is None:
            continue
        rows.append(
            {
                "id": issue["number"],
                "title": issue["title"],
                "body": issue.get("body") or "",
                "label": label,
                "created_at": issue["created_at"],
            }
        )

    df = pd.DataFrame(rows)
    df["text"] = df["title"] + " " + df["body"].fillna("")
    df = (
        df.drop_duplicates(subset=["id"])
        .sort_values("created_at")
        .reset_index(drop=True)
    )

    print(f"labeled issues: {len(df)}")
    print(df["label"].value_counts().to_string())

    # Temporal split: test = newest 15%
    cutoff = int(len(df) * 0.85)
    train_val = df.iloc[:cutoff]
    test = df.iloc[cutoff:]

    train, val = train_test_split(
        train_val, test_size=0.15, stratify=train_val["label"], random_state=42
    )
    train = train.reset_index(drop=True)
    val = val.reset_index(drop=True)
    test = test.reset_index(drop=True)

    train.to_csv(out / "train.csv", index=False)
    val.to_csv(out / "val.csv", index=False)
    test.to_csv(out / "test.csv", index=False)
    print(f"splits — train:{len(train)}, val:{len(val)}, test:{len(test)}")

    # Preprocess (same logic as preprocess.py)
    import re as _re

    def clean(text: str) -> str:
        text = _re.sub(r"<[^>]+>", " ", text)
        text = _re.sub(r"```[\s\S]*?```", " [CODE] ", text)
        text = _re.sub(r"`[^`]+`", " [CODE] ", text)
        text = _re.sub(r"https?://\S+", " [URL] ", text)
        text = _re.sub(r"\s+", " ", text).strip()
        return text[:2000]

    for split_df, name in [(train, "train"), (val, "val"), (test, "test")]:
        c = split_df.copy()
        c["title_clean"] = c["title"].fillna("").apply(clean)
        c["body_clean"] = c["body"].fillna("").apply(clean)
        c["text_clean"] = (
            c["title_clean"] + " " + c["title_clean"] + " " + c["body_clean"]
        ).apply(lambda t: _re.sub(r"\s+", " ", t).strip()[:2000])
        c.to_csv(out / f"{name}_clean.csv", index=False)
        print(f"preprocessed {name}: {len(c)} rows")

    print("done — all dataset files written to datasets/")


if __name__ == "__main__":
    main()
