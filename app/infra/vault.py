import os
import time
import hvac
from app.domain.exceptions import VaultUnavailableError

_secrets: dict[str, str] = {}

_RETRIES = 10
_RETRY_DELAY = 3.0


def load_secrets() -> None:
    """Pull all app secrets from Vault at startup. Retries up to _RETRIES times."""
    addr = os.environ["VAULT_ADDR"]
    token = os.environ["VAULT_ROOT_TOKEN"]

    last_exc: Exception | None = None
    for attempt in range(1, _RETRIES + 1):
        try:
            client = hvac.Client(url=addr, token=token)
            if not client.is_authenticated():
                raise VaultUnavailableError("Vault authentication failed")
            data = client.secrets.kv.v2.read_secret_version(
                path="app", mount_point="secret"
            )
            _secrets.update(data["data"]["data"])
            return
        except VaultUnavailableError:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt < _RETRIES:
                time.sleep(_RETRY_DELAY)

    raise VaultUnavailableError(
        f"Cannot reach Vault at {addr}: {last_exc}"
    ) from last_exc


def get(key: str) -> str:
    """Return a secret by key. Raises KeyError if not loaded."""
    return _secrets[key]
