import os
from pathlib import Path


def load_dotenv_if_present():
    """Load simple KEY=VALUE pairs from .env files without extra dependencies."""
    for path in dotenv_candidates():
        if not path.is_file():
            continue

        with path.open("r") as f:
            for raw_line in f:
                line = raw_line.strip()

                if not line or line.startswith("#") or "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip("\"'")

                if key and key not in os.environ:
                    os.environ[key] = value


def dotenv_candidates():
    package_file = Path(__file__).resolve()
    code_dir = package_file.parents[1]
    repo_dir = package_file.parents[2]

    return [
        code_dir / ".env",
        repo_dir / ".env",
    ]
