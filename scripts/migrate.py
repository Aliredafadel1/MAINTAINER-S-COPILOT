"""Pulls DB_PASSWORD from Vault, sets it in env, then runs Alembic upgrade head."""

import os
import sys
import hvac
from alembic.config import Config
from alembic import command

VAULT_ADDR = os.environ["VAULT_ADDR"]
VAULT_TOKEN = os.environ["VAULT_ROOT_TOKEN"]

try:
    client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)
    data = client.secrets.kv.v2.read_secret_version(path="app", mount_point="secret")
    os.environ["DB_PASSWORD"] = data["data"]["data"]["DB_PASSWORD"]
except Exception as exc:
    print(f"cannot read DB_PASSWORD from Vault: {exc}", file=sys.stderr)
    sys.exit(1)

cfg = Config("alembic.ini")
command.upgrade(cfg, "head")
print("migrations complete")
