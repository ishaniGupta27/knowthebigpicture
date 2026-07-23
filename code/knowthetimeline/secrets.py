import json
import os
from functools import lru_cache
from pathlib import Path

from .env import load_dotenv_if_present
from .errors import KttError
from .settings import BASE_DIR


DEFAULT_SECRETS_PATH = BASE_DIR / "secrets" / "knowthetimeline.secrets.json"


@lru_cache(maxsize=4)
def load_secret_file(path=None):
    secret_path = Path(path or DEFAULT_SECRETS_PATH)
    if not secret_path.is_file():
        return {}

    try:
        with secret_path.open("r") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise KttError(f"Invalid secrets JSON: {secret_path}: {e}") from e

    if not isinstance(data, dict):
        raise KttError(f"Secrets file must contain a JSON object: {secret_path}")

    return data


def secret_value(name, required=False, secrets_path=None):
    load_dotenv_if_present()
    secrets = load_secret_file(secrets_path)
    value = secrets.get(name)

    if isinstance(value, str) and value.strip():
        return value

    value = os.environ.get(name)
    if value:
        return value

    if required:
        raise KttError(
            f"Missing {name}. Add it to {DEFAULT_SECRETS_PATH} or set env var {name}."
        )

    return None


def export_secret_to_env(name, required=False, secrets_path=None):
    value = secret_value(name, required=required, secrets_path=secrets_path)
    if value:
        os.environ[name] = value
    return value
