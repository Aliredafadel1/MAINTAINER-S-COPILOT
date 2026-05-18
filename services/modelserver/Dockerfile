FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Install CPU-only torch first — avoids downloading 2GB+ of CUDA libs.
# --retries 5 survives transient network blips; --timeout 300 for slow links.
RUN pip install --no-cache-dir --timeout 300 --retries 5 \
    torch==2.4.1+cpu \
    --extra-index-url https://download.pytorch.org/whl/cpu
# Install the rest; extra-index-url ensures sentence-transformers also picks
# CPU torch wheels instead of re-pulling the GPU variant.
RUN pip install --no-cache-dir --timeout 300 --retries 5 \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt

COPY . .

# prompts/ is mounted from project root via compose volume
ENV PYTHONUNBUFFERED=1
