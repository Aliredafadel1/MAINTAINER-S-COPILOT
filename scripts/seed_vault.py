"""Runs once at stack startup to seed all app secrets into Vault."""

import os
import sys
import hvac

VAULT_ADDR = os.environ["VAULT_ADDR"]
VAULT_TOKEN = os.environ["VAULT_ROOT_TOKEN"]

SECRETS = {
    "DB_PASSWORD": os.environ.get("SEED_DB_PASSWORD", "changeme"),
    "LLM_API_KEY": os.environ.get("SEED_LLM_API_KEY", "sk-placeholder"),
    "JWT_SECRET": os.environ.get("SEED_JWT_SECRET", "super-secret-jwt-key-change-me"),
    "MINIO_ACCESS_KEY": os.environ.get("SEED_MINIO_ACCESS_KEY", "minioadmin"),
    "MINIO_SECRET_KEY": os.environ.get("SEED_MINIO_SECRET_KEY", "minioadmin"),
    "TRACING_KEY": os.environ.get("SEED_TRACING_KEY", ""),
}

try:
    client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)
    client.secrets.kv.v2.create_or_update_secret(
        path="app", secret=SECRETS, mount_point="secret"
    )
    print("vault seeded successfully")
except Exception as exc:
    print(f"vault seed failed: {exc}", file=sys.stderr)
    sys.exit(1)
