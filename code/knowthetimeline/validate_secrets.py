import argparse
import os
import subprocess

from .env import load_dotenv_if_present
from .errors import KttError
from .remote import configure_rclone_from_secret, rclone_bin_from_env
from .secrets import secret_value
from .youtube import access_token


def masked(value):
    if not value:
        return "missing"
    if len(value) <= 8:
        return "present"
    return f"present ({value[:4]}...{value[-4:]})"


def require_present(name):
    value = secret_value(name)
    if not value:
        raise KttError(
            f"Missing {name}. Add it to secrets/knowthetimeline.secrets.json "
            f"or set env var {name}."
        )
    print(f"OK {name}: {masked(value)}")
    return value


def validate_openai():
    import requests

    api_key = require_present("OPENAI_API_KEY")
    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": secret_value("OPENAI_MODEL") or "gpt-5-mini",
            "input": "Return exactly: ok",
            "max_output_tokens": 16,
        },
        timeout=60,
    )
    if response.status_code >= 400:
        raise KttError(
            f"OpenAI validation failed: HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )
    print("OK OPENAI_API_KEY validated with OpenAI")


def validate_youtube():
    require_present("YOUTUBE_CLIENT_ID")
    require_present("YOUTUBE_CLIENT_SECRET")
    require_present("YOUTUBE_REFRESH_TOKEN")
    token = access_token()
    print(f"OK YouTube refresh token exchanged: {masked(token)}")


def validate_rclone(remote_root):
    require_present("RCLONE_CONFIG")
    configure_rclone_from_secret()
    rclone_bin = rclone_bin_from_env()
    command = [rclone_bin, "lsd", remote_root]
    print(f"Checking rclone remote: {remote_root}")
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as e:
        raise KttError(
            "rclone was not found. Install rclone or set KTT_RCLONE_BIN."
        ) from e
    except subprocess.CalledProcessError as e:
        raise KttError(f"rclone validation failed for {remote_root}") from e
    print("OK RCLONE_CONFIG validated with rclone")


def main(argv=None):
    load_dotenv_if_present()
    parser = argparse.ArgumentParser(
        description="Validate KnowTheTimeline secrets without rendering or uploading."
    )
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--openai", action="store_true")
    parser.add_argument("--youtube", action="store_true")
    parser.add_argument("--rclone", action="store_true")
    parser.add_argument(
        "--remote-root",
        default=os.environ.get("KTT_REMOTE_ROOT", "gdrive:knowthetimeline"),
    )
    args = parser.parse_args(argv)

    if not any([args.all, args.openai, args.youtube, args.rclone]):
        args.openai = True
        args.youtube = True

    try:
        if args.all or args.openai:
            validate_openai()
        if args.all or args.youtube:
            validate_youtube()
        if args.all or args.rclone:
            validate_rclone(args.remote_root)
    except KttError as e:
        print(f"ERROR: {e}")
        return 1

    print("DONE secrets validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
