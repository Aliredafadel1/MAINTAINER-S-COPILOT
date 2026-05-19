FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Install torch BEFORE copying requirements.txt so this layer stays cached
# even when requirements.txt changes. Torch is ~2GB — we never want to re-download it.
RUN pip install --no-cache-dir --timeout 300 --retries 5 \
    torch==2.4.1+cpu \
    --extra-index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 300 --retries 5 \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt
# setuptools must come last — pip's resolver can downgrade it during the main install
RUN pip install --no-cache-dir "setuptools>=70.0.0,<72"

COPY . .

ENV PYTHONUNBUFFERED=1
