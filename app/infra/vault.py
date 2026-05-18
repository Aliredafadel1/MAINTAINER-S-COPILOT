import os
import hvac
from app.domain.exceptions import VaultUnavailableError

_secrets: dict[str, str] = {}


def load_secrets() -> None:
    """Pull all app secrets from Vault at startup. Raises VaultUnavailableError on failure."""
    addr = os.environ["VAULT_ADDR"]
    token = os.environ["VAULT_ROOT_TOKEN"]

    try:
        client = hvac.Client(url=addr, token=token)
        if not client.is_authenticated():
            raise VaultUnavailableError("Vault authentication failed")

        data = client.secrets.kv.v2.read_secret_version(
            path="app", mount_point="secret"
        )
        _secrets.update(data["data"]["data"])
    except VaultUnavailableError:
        raise
    except Exception as exc:
        raise VaultUnavailableError(f"Cannot reach Vault at {addr}: {exc}") from exc


def get(key: str) -> str:
    """Return a secret by key. Raises KeyError if not loaded."""
    return _secrets[key]
