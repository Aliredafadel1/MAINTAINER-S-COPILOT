"""Seed a synthetic RAG corpus and build evals/golden/rag_golden.json.

Run once after `docker compose up` to populate corpus_chunks and write
the 25-entry golden evaluation set with real DB chunk UUIDs.

Usage (from project root):
    DB_PASSWORD=changeme python scripts/seed_and_build_golden.py
"""

import json
import os

import psycopg2
import psycopg2.extras
import requests

MODELSERVER_URL = os.environ.get("MODELSERVER_URL", "http://localhost:8001")
GOLDEN_PATH = "evals/golden/rag_golden.json"

# ── Synthetic corpus ──────────────────────────────────────────────────────────
# 15 doc chunks + 10 issue chunks — each chunk is the primary answer for one
# golden question so hit@5 is measurable on a cold corpus.

CORPUS: list[dict] = [
    # ── README / install ──
    {
        "source_type": "docs",
        "source_id": "README.md",
        "chunk_index": 0,
        "content": (
            "# transformers-toolkit\n\n"
            "A high-level Python library for working with Hugging Face models. "
            "Install with pip:\n\n"
            "    pip install transformers-toolkit\n\n"
            "Requires Python 3.9+ and PyTorch 2.0 or TensorFlow 2.12."
        ),
        "metadata": {"path": "README.md"},
    },
    {
        "source_type": "docs",
        "source_id": "README.md",
        "chunk_index": 1,
        "content": (
            "## Quick start\n\n"
            "```python\n"
            "from transformers_toolkit import Pipeline\n\n"
            "pipe = Pipeline('text-classification')\n"
            "result = pipe('This movie was fantastic!')\n"
            "print(result)  # {'label': 'POSITIVE', 'score': 0.9998}\n"
            "```\n\n"
            "The Pipeline class auto-downloads the default model on first use."
        ),
        "metadata": {"path": "README.md"},
    },
    # ── Configuration ──
    {
        "source_type": "docs",
        "source_id": "docs/configuration.md",
        "chunk_index": 0,
        "content": (
            "## Request timeout\n\n"
            "Set `timeout` (seconds) when creating a client:\n\n"
            "    client = Client(timeout=30)\n\n"
            "Or per-request: `client.predict(text, timeout=10)`. "
            "Default is 60 seconds. Set to `None` to disable."
        ),
        "metadata": {"path": "docs/configuration.md"},
    },
    {
        "source_type": "docs",
        "source_id": "docs/configuration.md",
        "chunk_index": 1,
        "content": (
            "## Retry policy\n\n"
            "Automatic retries use exponential back-off. Configure via:\n\n"
            "    client = Client(max_retries=3, backoff_factor=0.5)\n\n"
            "`backoff_factor` controls the delay between retries: "
            "delay = backoff_factor * (2 ** attempt). "
            "Set `max_retries=0` to disable retries entirely."
        ),
        "metadata": {"path": "docs/configuration.md"},
    },
    # ── API reference ──
    {
        "source_type": "docs",
        "source_id": "docs/api_reference.md",
        "chunk_index": 0,
        "content": (
            "## Authentication\n\n"
            "Pass your API key at client creation or via environment variable:\n\n"
            "    client = Client(api_key='hf_...')\n"
            "    # or\n"
            "    export TRANSFORMERS_TOOLKIT_API_KEY=hf_...\n\n"
            "Keys are never logged. Rotate them in the Hugging Face settings page."
        ),
        "metadata": {"path": "docs/api_reference.md"},
    },
    {
        "source_type": "docs",
        "source_id": "docs/api_reference.md",
        "chunk_index": 1,
        "content": (
            "## Async client\n\n"
            "Use `AsyncClient` for `asyncio`-based applications:\n\n"
            "    async with AsyncClient() as client:\n"
            "        result = await client.predict(text)\n\n"
            "The async client reuses a single `aiohttp.ClientSession` internally "
            "and is safe to share across coroutines."
        ),
        "metadata": {"path": "docs/api_reference.md"},
    },
    {
        "source_type": "docs",
        "source_id": "docs/api_reference.md",
        "chunk_index": 2,
        "content": (
            "## Batch processing\n\n"
            "Pass a list of inputs to `predict_batch` for efficient throughput:\n\n"
            "    results = client.predict_batch(texts, batch_size=32)\n\n"
            "Batches are chunked automatically. "
            "`batch_size=32` is the default and works well for most GPU memory sizes."
        ),
        "metadata": {"path": "docs/api_reference.md"},
    },
    # ── Troubleshooting ──
    {
        "source_type": "docs",
        "source_id": "docs/troubleshooting.md",
        "chunk_index": 0,
        "content": (
            "## ConnectionError\n\n"
            "If you see `ConnectionError: HTTPSConnectionPool host unreachable`, check:\n\n"
            "1. The server address is correct (`TRANSFORMERS_TOOLKIT_BASE_URL`).\n"
            "2. Your network allows outbound HTTPS on port 443.\n"
            "3. Set `verify_ssl=False` only as a last resort (disables certificate checks).\n"
            "4. Increase `max_retries` and add `backoff_factor=1.0` for flaky connections."
        ),
        "metadata": {"path": "docs/troubleshooting.md"},
    },
    {
        "source_type": "docs",
        "source_id": "docs/troubleshooting.md",
        "chunk_index": 1,
        "content": (
            "## Memory management\n\n"
            "To reduce peak memory when processing large datasets:\n\n"
            "- Use a generator instead of a list: `predict_batch(iter(texts))`.\n"
            "- Lower `batch_size` to 8 or 16.\n"
            "- Call `model.half()` to use FP16 weights (halves VRAM usage).\n"
            "- Enable gradient checkpointing: `model.gradient_checkpointing_enable()`."
        ),
        "metadata": {"path": "docs/troubleshooting.md"},
    },
    {
        "source_type": "docs",
        "source_id": "docs/troubleshooting.md",
        "chunk_index": 2,
        "content": (
            "## CUDA setup\n\n"
            "GPU acceleration requires a CUDA-compatible PyTorch build:\n\n"
            "    pip install torch --index-url https://download.pytorch.org/whl/cu121\n\n"
            "Verify with `torch.cuda.is_available()`. "
            "Pass `device='cuda'` to `Pipeline` or `Client` to use the GPU."
        ),
        "metadata": {"path": "docs/troubleshooting.md"},
    },
    # ── Contributing ──
    {
        "source_type": "docs",
        "source_id": "CONTRIBUTING.md",
        "chunk_index": 0,
        "content": (
            "## Running the test suite\n\n"
            "Install dev dependencies and run pytest:\n\n"
            "    pip install -e '.[dev]'\n"
            "    pytest tests/ -v --cov=transformers_toolkit\n\n"
            "Integration tests require `TRANSFORMERS_TOOLKIT_API_KEY` to be set. "
            "Skip them with `-m 'not integration'`."
        ),
        "metadata": {"path": "CONTRIBUTING.md"},
    },
    {
        "source_type": "docs",
        "source_id": "CONTRIBUTING.md",
        "chunk_index": 1,
        "content": (
            "## Pull request requirements\n\n"
            "Before opening a PR ensure:\n\n"
            "1. All existing tests pass (`pytest`).\n"
            "2. New code has ≥ 90 % test coverage.\n"
            "3. `ruff check` and `mypy` report no errors.\n"
            "4. Changelog updated in `CHANGELOG.md`.\n"
            "5. PR description includes a summary and a test plan."
        ),
        "metadata": {"path": "CONTRIBUTING.md"},
    },
    # ── Migration ──
    {
        "source_type": "docs",
        "source_id": "docs/migration_v2.md",
        "chunk_index": 0,
        "content": (
            "## Breaking changes in v2\n\n"
            "- `Pipeline(task)` replaces `Classifier(task)` — rename all usages.\n"
            "- `client.run()` renamed to `client.predict()` — update call sites.\n"
            "- The `use_fast` tokenizer parameter is removed; fast tokenizers are "
            "  now always used. Remove `use_fast=True/False` from all code.\n"
            "- Minimum Python version raised from 3.8 to 3.9."
        ),
        "metadata": {"path": "docs/migration_v2.md"},
    },
    # ── Performance ──
    {
        "source_type": "docs",
        "source_id": "docs/performance.md",
        "chunk_index": 0,
        "content": (
            "## Caching model outputs\n\n"
            "Enable the built-in LRU cache to avoid re-computing identical inputs:\n\n"
            "    client = Client(cache_size=1000)  # cache last 1000 results\n\n"
            "Results are keyed by input text hash. "
            "Disable with `cache_size=0`. "
            "The cache is in-process and not shared across workers."
        ),
        "metadata": {"path": "docs/performance.md"},
    },
    {
        "source_type": "docs",
        "source_id": "docs/performance.md",
        "chunk_index": 1,
        "content": (
            "## Concurrency settings\n\n"
            "The async client supports configurable connection pool size:\n\n"
            "    client = AsyncClient(max_connections=20, max_keepalive=10)\n\n"
            "For CPU-bound workloads run multiple workers with `multiprocessing`. "
            "Set `num_workers` on `Pipeline` to parallelize inference across cores."
        ),
        "metadata": {"path": "docs/performance.md"},
    },
    # ── Issues ──
    {
        "source_type": "issue",
        "source_id": "142",
        "chunk_index": 0,
        "content": (
            "Title: ConnectionError when using async client with retry=3\n\n"
            "Using transformers-toolkit 4.35.0 on Python 3.11. "
            "When I call pipeline('text-classification') and the hub is slow, "
            "I get ConnectionError after exactly 3 retries even though I set "
            "TRANSFORMERS_OFFLINE=0.\n\n"
            "Resolution: TRANSFORMERS_OFFLINE only affects model downloads, not "
            "inference requests. The fix is to set `backoff_factor=1.0` in the "
            "client constructor so retries wait longer between attempts: "
            "`Client(max_retries=5, backoff_factor=1.0)`."
        ),
        "metadata": {
            "title": "ConnectionError when using async client with retry=3",
            "issue_id": "142",
        },
    },
    {
        "source_type": "issue",
        "source_id": "201",
        "chunk_index": 0,
        "content": (
            "Title: TypeError when passing list to encode()\n\n"
            "Calling `tokenizer.encode(['hello', 'world'])` raises "
            "TypeError: expected str, got list.\n\n"
            "Resolution: Use `tokenizer.encode_batch(['hello', 'world'])` "
            "for lists of strings. The `encode()` method accepts a single string only. "
            "This is consistent with the HuggingFace tokenizers API."
        ),
        "metadata": {
            "title": "TypeError when passing list to encode()",
            "issue_id": "201",
        },
    },
    {
        "source_type": "issue",
        "source_id": "287",
        "chunk_index": 0,
        "content": (
            "Title: Memory leak in batch processing loop\n\n"
            "When calling `predict_batch` in a loop, RSS memory grows ~50 MB "
            "per iteration and is never freed.\n\n"
            "Resolution: The pipeline was accumulating hidden states in a list. "
            "Fixed in v4.36.1. Workaround for older versions: call "
            "`torch.cuda.empty_cache()` and `gc.collect()` after each batch, "
            "or use a context manager: `with client.no_cache(): ...`"
        ),
        "metadata": {
            "title": "Memory leak in batch processing loop",
            "issue_id": "287",
        },
    },
    {
        "source_type": "issue",
        "source_id": "334",
        "chunk_index": 0,
        "content": (
            "Title: Tokenizer raises UnicodeEncodeError on emoji and special characters\n\n"
            "Text containing emoji (e.g. 🎉) or CJK characters causes "
            "UnicodeEncodeError in the fast tokenizer.\n\n"
            "Resolution: Ensure your Python environment uses UTF-8 locale. "
            "Set `PYTHONIOENCODING=utf-8`. The tokenizer handles Unicode natively "
            "since v4.34; upgrade if on an older version. "
            "Pass `clean_up_tokenization_spaces=True` as a workaround."
        ),
        "metadata": {
            "title": "Tokenizer raises UnicodeEncodeError on emoji",
            "issue_id": "334",
        },
    },
    {
        "source_type": "issue",
        "source_id": "391",
        "chunk_index": 0,
        "content": (
            "Title: CUDA out of memory during inference with large batch\n\n"
            "RuntimeError: CUDA out of memory. Tried to allocate 2.50 GiB. "
            "Happens with batch_size=64 on a 16 GB GPU.\n\n"
            "Resolution: Reduce batch_size to 8–16. Enable FP16: "
            "`model.half().cuda()`. Use `torch.no_grad()` context to prevent "
            "gradient accumulation. If still OOM, enable CPU offload: "
            "`pipeline(device_map='auto')`."
        ),
        "metadata": {"title": "CUDA out of memory during inference", "issue_id": "391"},
    },
    {
        "source_type": "issue",
        "source_id": "445",
        "chunk_index": 0,
        "content": (
            "Title: First model.load() call takes 30+ seconds\n\n"
            "The initial call to `model.load('bert-base-uncased')` takes over "
            "30 seconds. Subsequent calls are instant.\n\n"
            "Resolution: First load downloads weights from the Hub (~400 MB). "
            "Subsequent calls use the local cache at `~/.cache/huggingface/hub`. "
            "Pre-download with: `python -c "
            "\"from transformers import AutoModel; AutoModel.from_pretrained('bert-base-uncased')\"`"
            ". In Docker, mount the HF cache as a volume."
        ),
        "metadata": {
            "title": "First model.load() call takes 30+ seconds",
            "issue_id": "445",
        },
    },
    {
        "source_type": "issue",
        "source_id": "512",
        "chunk_index": 0,
        "content": (
            "Title: UserWarning: use_fast parameter is deprecated\n\n"
            "Getting warning: UserWarning: The `use_fast` argument is deprecated "
            "and will be removed in a future version.\n\n"
            "Resolution: Remove `use_fast=True` or `use_fast=False` from all "
            "tokenizer calls. Fast tokenizers are always used in v2+. "
            "See the v2 migration guide for the full list of removed parameters."
        ),
        "metadata": {"title": "use_fast parameter is deprecated", "issue_id": "512"},
    },
    {
        "source_type": "issue",
        "source_id": "601",
        "chunk_index": 0,
        "content": (
            "Title: Rate limit handling in async mode\n\n"
            "In async code, hitting the API rate limit raises RateLimitError "
            "immediately instead of waiting and retrying.\n\n"
            "Resolution: The async client respects `Retry-After` headers since v4.37. "
            "Upgrade to get automatic rate-limit retry. For older versions, catch "
            "RateLimitError and use `asyncio.sleep(retry_after)` manually."
        ),
        "metadata": {"title": "Rate limit handling in async mode", "issue_id": "601"},
    },
    {
        "source_type": "issue",
        "source_id": "678",
        "chunk_index": 0,
        "content": (
            "Title: SSLError: certificate verify failed\n\n"
            "Getting SSLError: [SSL: CERTIFICATE_VERIFY_FAILED] when connecting "
            "behind a corporate proxy.\n\n"
            "Resolution: Set the CA bundle path: "
            "`REQUESTS_CA_BUNDLE=/path/to/corporate-ca.crt`. "
            "Or add the certificate to the system trust store. "
            "Do NOT use `verify=False` in production — it disables all TLS verification."
        ),
        "metadata": {"title": "SSLError: certificate verify failed", "issue_id": "678"},
    },
    {
        "source_type": "issue",
        "source_id": "723",
        "chunk_index": 0,
        "content": (
            "Title: DataLoader hangs with num_workers > 0\n\n"
            "Using `DataLoader(dataset, num_workers=4)` causes the process to hang "
            "indefinitely when combined with the pipeline's multiprocessing.\n\n"
            "Resolution: This is a known Python multiprocessing deadlock when forking "
            "with initialized CUDA context. Fix: set `multiprocessing_context='spawn'` "
            "on DataLoader, or set `num_workers=0` for the DataLoader and use "
            "`Pipeline(num_workers=4)` instead."
        ),
        "metadata": {
            "title": "DataLoader hangs with num_workers > 0",
            "issue_id": "723",
        },
    },
]

# ── Golden questions ───────────────────────────────────────────────────────────
# Each entry maps to exactly one corpus chunk via (source_type, source_id, chunk_index).

GOLDEN_TEMPLATE: list[dict] = [
    {
        "id": "rag-001",
        "question": "How do I install transformers-toolkit?",
        "ideal_answer": "Install with pip: pip install transformers-toolkit. Requires Python 3.9+ and PyTorch 2.0 or TensorFlow 2.12.",
        "relevant": ("docs", "README.md", 0),
        "hand_labeled": True,
    },
    {
        "id": "rag-002",
        "question": "Can you show me a basic example of using the Pipeline?",
        "ideal_answer": "Create a Pipeline with the task name and call it with your input text. It auto-downloads the default model on first use.",
        "relevant": ("docs", "README.md", 1),
        "hand_labeled": True,
    },
    {
        "id": "rag-003",
        "question": "How do I set the request timeout for API calls?",
        "ideal_answer": "Set timeout in seconds when creating a client: Client(timeout=30). You can also pass timeout per-request.",
        "relevant": ("docs", "docs/configuration.md", 0),
        "hand_labeled": True,
    },
    {
        "id": "rag-004",
        "question": "How do I configure automatic retries with exponential back-off?",
        "ideal_answer": "Use max_retries and backoff_factor: Client(max_retries=3, backoff_factor=0.5). Delay is backoff_factor * 2^attempt.",
        "relevant": ("docs", "docs/configuration.md", 1),
        "hand_labeled": False,
    },
    {
        "id": "rag-005",
        "question": "How do I authenticate with an API key?",
        "ideal_answer": "Pass api_key at client creation or set the TRANSFORMERS_TOOLKIT_API_KEY environment variable.",
        "relevant": ("docs", "docs/api_reference.md", 0),
        "hand_labeled": False,
    },
    {
        "id": "rag-006",
        "question": "How do I use the async client in an asyncio application?",
        "ideal_answer": "Use AsyncClient as an async context manager with `async with AsyncClient() as client: result = await client.predict(text)`.",
        "relevant": ("docs", "docs/api_reference.md", 1),
        "hand_labeled": False,
    },
    {
        "id": "rag-007",
        "question": "How do I process multiple items efficiently with batching?",
        "ideal_answer": "Use predict_batch with a list of inputs and set batch_size=32. Batches are chunked automatically.",
        "relevant": ("docs", "docs/api_reference.md", 2),
        "hand_labeled": False,
    },
    {
        "id": "rag-008",
        "question": "How do I fix ConnectionError when connecting to the server?",
        "ideal_answer": "Check server address, allow outbound HTTPS port 443, increase max_retries with backoff_factor=1.0.",
        "relevant": ("docs", "docs/troubleshooting.md", 0),
        "hand_labeled": True,
    },
    {
        "id": "rag-009",
        "question": "How do I reduce memory usage when processing large datasets?",
        "ideal_answer": "Use a generator instead of a list, lower batch_size, call model.half() for FP16, or enable gradient checkpointing.",
        "relevant": ("docs", "docs/troubleshooting.md", 1),
        "hand_labeled": False,
    },
    {
        "id": "rag-010",
        "question": "How do I set up CUDA for GPU acceleration?",
        "ideal_answer": "Install CUDA-compatible PyTorch, verify with torch.cuda.is_available(), then pass device='cuda' to Pipeline or Client.",
        "relevant": ("docs", "docs/troubleshooting.md", 2),
        "hand_labeled": False,
    },
    {
        "id": "rag-011",
        "question": "How do I run the test suite for this project?",
        "ideal_answer": "Install dev dependencies with pip install -e '.[dev]' then run pytest tests/ -v --cov=transformers_toolkit.",
        "relevant": ("docs", "CONTRIBUTING.md", 0),
        "hand_labeled": True,
    },
    {
        "id": "rag-012",
        "question": "What are the requirements for opening a pull request?",
        "ideal_answer": "All tests must pass, ≥90% coverage, ruff and mypy clean, changelog updated, PR description with summary and test plan.",
        "relevant": ("docs", "CONTRIBUTING.md", 1),
        "hand_labeled": False,
    },
    {
        "id": "rag-013",
        "question": "What breaking changes were introduced in version 2?",
        "ideal_answer": "Pipeline replaces Classifier, predict() replaces run(), use_fast parameter removed, minimum Python raised to 3.9.",
        "relevant": ("docs", "docs/migration_v2.md", 0),
        "hand_labeled": True,
    },
    {
        "id": "rag-014",
        "question": "How do I cache model outputs to improve performance?",
        "ideal_answer": "Pass cache_size to the Client constructor: Client(cache_size=1000). Results are keyed by input text hash.",
        "relevant": ("docs", "docs/performance.md", 0),
        "hand_labeled": False,
    },
    {
        "id": "rag-015",
        "question": "How do I configure the number of concurrent connections in async mode?",
        "ideal_answer": "Use max_connections and max_keepalive on AsyncClient: AsyncClient(max_connections=20, max_keepalive=10).",
        "relevant": ("docs", "docs/performance.md", 1),
        "hand_labeled": False,
    },
    {
        "id": "rag-016",
        "question": "I get ConnectionError after 3 retries even with TRANSFORMERS_OFFLINE=0. What is the fix?",
        "ideal_answer": "TRANSFORMERS_OFFLINE only affects model downloads. Set backoff_factor=1.0 and increase max_retries: Client(max_retries=5, backoff_factor=1.0).",
        "relevant": ("issue", "142", 0),
        "hand_labeled": True,
    },
    {
        "id": "rag-017",
        "question": "TypeError when passing a list of strings to tokenizer encode method",
        "ideal_answer": "Use encode_batch(['hello', 'world']) for lists. The encode() method only accepts a single string.",
        "relevant": ("issue", "201", 0),
        "hand_labeled": False,
    },
    {
        "id": "rag-018",
        "question": "Memory grows with each batch call and is never freed. How do I fix the memory leak?",
        "ideal_answer": "Upgrade to v4.36.1 which fixes the leak. Workaround: call torch.cuda.empty_cache() and gc.collect() after each batch.",
        "relevant": ("issue", "287", 0),
        "hand_labeled": True,
    },
    {
        "id": "rag-019",
        "question": "UnicodeEncodeError when tokenizing text with emoji or CJK characters",
        "ideal_answer": "Set PYTHONIOENCODING=utf-8, upgrade to v4.34+, or pass clean_up_tokenization_spaces=True as a workaround.",
        "relevant": ("issue", "334", 0),
        "hand_labeled": False,
    },
    {
        "id": "rag-020",
        "question": "RuntimeError CUDA out of memory during model inference with large batch size",
        "ideal_answer": "Reduce batch_size to 8-16, enable FP16 with model.half(), use torch.no_grad(), or set device_map='auto' for CPU offload.",
        "relevant": ("issue", "391", 0),
        "hand_labeled": True,
    },
    {
        "id": "rag-021",
        "question": "Why does the first model load call take over 30 seconds?",
        "ideal_answer": "The first call downloads weights from Hugging Face Hub. Pre-download them and mount ~/.cache/huggingface/hub as a Docker volume.",
        "relevant": ("issue", "445", 0),
        "hand_labeled": False,
    },
    {
        "id": "rag-022",
        "question": "How do I fix the use_fast deprecated parameter warning?",
        "ideal_answer": "Remove use_fast=True or use_fast=False from all tokenizer calls. Fast tokenizers are always used in v2+.",
        "relevant": ("issue", "512", 0),
        "hand_labeled": False,
    },
    {
        "id": "rag-023",
        "question": "How does the library handle API rate limits in async mode?",
        "ideal_answer": "Since v4.37 the async client reads Retry-After headers and waits automatically. For older versions catch RateLimitError and sleep manually.",
        "relevant": ("issue", "601", 0),
        "hand_labeled": False,
    },
    {
        "id": "rag-024",
        "question": "SSLError certificate verify failed when connecting behind a corporate proxy",
        "ideal_answer": "Set REQUESTS_CA_BUNDLE to your corporate CA bundle path. Add the cert to the system trust store. Do not use verify=False in production.",
        "relevant": ("issue", "678", 0),
        "hand_labeled": False,
    },
    {
        "id": "rag-025",
        "question": "DataLoader hangs indefinitely when num_workers is greater than zero",
        "ideal_answer": "Set multiprocessing_context='spawn' on DataLoader, or use num_workers=0 on DataLoader and Pipeline(num_workers=4) instead.",
        "relevant": ("issue", "723", 0),
        "hand_labeled": False,
    },
]


# ── Embedding ──────────────────────────────────────────────────────────────────


def embed_batch(texts: list[str]) -> list[list[float]]:
    resp = requests.post(
        f"{MODELSERVER_URL}/embed/batch",
        json={"texts": texts},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]


# ── DB helpers ─────────────────────────────────────────────────────────────────


def get_db_conn():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=os.environ.get("DB_NAME", "copilot"),
        user=os.environ.get("DB_USER", "copilot"),
        password=os.environ.get("DB_PASSWORD", "changeme"),
    )


def seed_corpus(conn, chunks: list[dict]) -> None:
    """Delete existing synthetic chunks then insert fresh ones."""
    source_ids = list({c["source_id"] for c in chunks})
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM corpus_chunks WHERE source_id = ANY(%s)",
            (source_ids,),
        )
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO corpus_chunks
                (source_type, source_id, chunk_index, content, metadata, embedding)
            VALUES %s
            """,
            [
                (
                    c["source_type"],
                    c["source_id"],
                    c["chunk_index"],
                    c["content"],
                    json.dumps(c["metadata"]),
                    c["embedding"],
                )
                for c in chunks
            ],
            template="(%s, %s, %s, %s, %s, %s::vector)",
        )
    conn.commit()


def fetch_chunk_id(conn, source_type: str, source_id: str, chunk_index: int) -> str:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id::text FROM corpus_chunks "
            "WHERE source_type=%s AND source_id=%s AND chunk_index=%s",
            (source_type, source_id, chunk_index),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError(
                f"chunk not found: {source_type}/{source_id}/{chunk_index}"
            )
        return row[0]


# ── Main ───────────────────────────────────────────────────────────────────────


def main() -> None:
    print(f"Embedding {len(CORPUS)} chunks via {MODELSERVER_URL}...")
    texts = [c["content"] for c in CORPUS]
    batch_size = 32
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        embeddings.extend(embed_batch(batch))
        print(f"  embedded {min(i + batch_size, len(texts))}/{len(texts)}")

    for chunk, vec in zip(CORPUS, embeddings):
        chunk["embedding"] = vec

    print("Seeding corpus into PostgreSQL...")
    conn = get_db_conn()
    seed_corpus(conn, CORPUS)
    print(f"  inserted {len(CORPUS)} chunks")

    print("Building golden set...")
    golden: list[dict] = []
    for entry in GOLDEN_TEMPLATE:
        src_type, src_id, chunk_idx = entry["relevant"]
        chunk_uuid = fetch_chunk_id(conn, src_type, src_id, chunk_idx)
        golden.append(
            {
                "id": entry["id"],
                "question": entry["question"],
                "ideal_answer": entry["ideal_answer"],
                "ground_truth_chunk_ids": [chunk_uuid],
                "hand_labeled": entry["hand_labeled"],
            }
        )
        print(f"  {entry['id']}: {chunk_uuid}")

    conn.close()

    import pathlib

    pathlib.Path(GOLDEN_PATH).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(GOLDEN_PATH).write_text(json.dumps(golden, indent=2))
    print(f"\nWrote {len(golden)} entries to {GOLDEN_PATH}")
    print("Done. Run `python evals/eval_rag.py` to evaluate.")


if __name__ == "__main__":
    main()
