"""Ingest RAG corpus: repo docs + held-out resolved issues.

Usage:
    GITHUB_TOKEN=...  DB_HOST=localhost  DB_PASSWORD=changeme  \
    MINIO_ENDPOINT=localhost:9000 MINIO_ACCESS_KEY=minioadmin MINIO_SECRET_KEY=minioadmin \
    python scripts/ingest_corpus.py --repo owner/repo --held-out datasets/test.csv
"""

import argparse
import json
import os
import sys
from uuid import uuid4

import psycopg2
import psycopg2.extras
import requests
from minio import Minio
from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64
BATCH_SIZE = 64


# ── Chunking ──────────────────────────────────────────────────────────────────


def _split(
    text: str, separators: list[str], chunk_size: int, overlap: int
) -> list[str]:
    if not text.strip():
        return []
    sep = separators[0]
    parts = text.split(sep) if sep else list(text)
    chunks, current = [], ""
    for part in parts:
        candidate = (current + sep + part).strip() if current else part.strip()
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            if len(part) > chunk_size and len(separators) > 1:
                chunks.extend(_split(part, separators[1:], chunk_size, overlap))
                current = ""
            else:
                current = part.strip()
    if current:
        chunks.append(current)
    # add overlap by prepending tail of previous chunk
    result = []
    for i, chunk in enumerate(chunks):
        if i > 0 and overlap:
            tail = chunks[i - 1][-overlap:]
            chunk = tail + " " + chunk
        result.append(chunk[: chunk_size + overlap])
    return result


def chunk_text(text: str) -> list[str]:
    return _split(text, ["\n\n", "\n", ". ", " "], CHUNK_SIZE, CHUNK_OVERLAP)


# ── GitHub helpers ─────────────────────────────────────────────────────────────


def _gh_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}


def fetch_markdown_files(repo: str, token: str) -> list[dict]:
    """Fetch all .md files from the repo recursively."""
    headers = _gh_headers(token)
    resp = requests.get(
        f"https://api.github.com/repos/{repo}/git/trees/HEAD?recursive=1",
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    tree = resp.json().get("tree", [])
    docs = []
    for item in tree:
        if item["type"] == "blob" and item["path"].endswith(".md"):
            raw = requests.get(
                f"https://raw.githubusercontent.com/{repo}/HEAD/{item['path']}",
                headers=headers,
                timeout=15,
            )
            if raw.status_code == 200:
                docs.append({"path": item["path"], "content": raw.text})
                print(f"  fetched doc: {item['path']}")
    return docs


def load_held_out_issues(csv_path: str) -> list[dict]:
    import pandas as pd

    df = pd.read_csv(csv_path)
    # Held-out issues are the test split — use issues that have a body
    df = df.dropna(subset=["body"])
    return df[["id", "title", "body"]].to_dict("records")


# ── Embedding + DB ─────────────────────────────────────────────────────────────


def embed_batch(model: SentenceTransformer, texts: list[str]) -> list[list[float]]:
    # BGE models benefit from a query prefix; for passages use no prefix
    vecs = model.encode(
        texts, normalize_embeddings=True, batch_size=BATCH_SIZE, show_progress_bar=False
    )
    return vecs.tolist()


def get_db_conn():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME", "copilot"),
        user=os.environ.get("DB_USER", "copilot"),
        password=os.environ["DB_PASSWORD"],
    )


def upsert_chunks(conn, rows: list[dict]) -> None:
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO corpus_chunks (id, source_type, source_id, chunk_index, content, metadata, embedding)
            VALUES %s
            ON CONFLICT DO NOTHING
            """,
            [
                (
                    str(uuid4()),
                    r["source_type"],
                    r["source_id"],
                    r["chunk_index"],
                    r["content"],
                    json.dumps(r["metadata"]),
                    r["embedding"],
                )
                for r in rows
            ],
            template="(%s, %s, %s, %s, %s, %s, %s::vector)",
        )
    conn.commit()


def store_raw_in_minio(chunks: list[dict]) -> None:
    client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=False,
    )
    bucket = "rag-corpus"
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    import io

    data = json.dumps(chunks, ensure_ascii=False).encode()
    client.put_object(
        bucket,
        "chunks_raw.json",
        io.BytesIO(data),
        len(data),
        content_type="application/json",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--held-out", required=True, help="test.csv path")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("GITHUB_TOKEN required", file=sys.stderr)
        sys.exit(1)

    print(f"loading embedding model {EMBEDDING_MODEL}...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    # ── Docs ──────────────────────────────────────────────────────────────────
    print("fetching repo docs...")
    docs = fetch_markdown_files(args.repo, token)
    doc_chunks: list[dict] = []
    for doc in docs:
        for i, chunk in enumerate(chunk_text(doc["content"])):
            doc_chunks.append(
                {
                    "source_type": "docs",
                    "source_id": doc["path"],
                    "chunk_index": i,
                    "content": chunk,
                    "metadata": {"path": doc["path"], "repo": args.repo},
                }
            )
    print(f"doc chunks: {len(doc_chunks)}")

    # ── Held-out issues ───────────────────────────────────────────────────────
    print("loading held-out issues...")
    issues = load_held_out_issues(args.held_out)
    issue_chunks: list[dict] = []
    for issue in issues:
        text = f"{issue['title']}\n\n{issue['body']}"
        for i, chunk in enumerate(chunk_text(text)):
            issue_chunks.append(
                {
                    "source_type": "issue",
                    "source_id": str(issue["id"]),
                    "chunk_index": i,
                    "content": chunk,
                    "metadata": {"title": issue["title"], "issue_id": issue["id"]},
                }
            )
    print(f"issue chunks: {len(issue_chunks)}")

    all_chunks = doc_chunks + issue_chunks
    print(f"total chunks: {len(all_chunks)} — embedding...")

    texts = [c["content"] for c in all_chunks]
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        vecs = embed_batch(model, batch)
        for chunk, vec in zip(all_chunks[i : i + BATCH_SIZE], vecs):
            chunk["embedding"] = vec
        print(f"  embedded {min(i + BATCH_SIZE, len(texts))}/{len(texts)}")

    print("storing raw chunks in MinIO...")
    store_raw_in_minio(all_chunks)

    print("upserting into postgres...")
    conn = get_db_conn()
    for i in range(0, len(all_chunks), 500):
        upsert_chunks(conn, all_chunks[i : i + 500])
        print(f"  inserted {min(i + 500, len(all_chunks))}/{len(all_chunks)}")
    conn.close()

    print("done")


if __name__ == "__main__":
    main()
