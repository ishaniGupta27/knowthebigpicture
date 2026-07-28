import argparse
import os
import subprocess

from .env import load_dotenv_if_present
from .errors import KtwError
from .remote import configure_rclone_from_secret, rclone_bin_from_env
from .secrets import secret_value


def masked(value):
    if not value:
        return "missing"
    if len(value) <= 8:
        return "present"
    return f"present ({value[:4]}...{value[-4:]})"


def require_present(name):
    value = secret_value(name)
    if not value:
        raise KtwError(
            f"Missing {name}. Add it to secrets/knowthebigpicture.secrets.json "
            f"or set env var {name}."
        )
    print(f"OK {name}: {masked(value)}")
    return value


def validate_gemini():
    from google import genai

    api_key = require_present("GEMINI_API_KEY")
    model = secret_value("GEMINI_MODEL") or "gemini-3.6-flash"
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model=model, contents="Return exactly: ok")
    text = (getattr(response, "text", "") or "").strip()
    if not text:
        raise KtwError("Gemini validation returned no text")
    print(f"OK GEMINI_API_KEY validated with Gemini ({model})")


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
        raise KtwError(
            f"OpenAI validation failed: HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )
    print("OK OPENAI_API_KEY validated with OpenAI")


def validate_youtube():
    from .youtube import access_token

    require_present("YOUTUBE_CLIENT_ID")
    require_present("YOUTUBE_CLIENT_SECRET")
    require_present("YOUTUBE_REFRESH_TOKEN")
    token = access_token()
    print(f"OK YouTube refresh token exchanged: {masked(token)}")


def validate_instagram():
    import requests

    token = require_present("INSTAGRAM_ACCESS_TOKEN").strip()
    configured_id = secret_value("INSTAGRAM_USER_ID")

    # Instagram-login tokens start with "IG" and use graph.instagram.com;
    # Facebook-login tokens start with "EAA" and use graph.facebook.com.
    base = (
        "https://graph.instagram.com"
        if token.startswith("IG")
        else "https://graph.facebook.com"
    )
    version = os.environ.get("IG_GRAPH_VERSION") or "v21.0"

    response = requests.get(
        f"{base}/{version}/me",
        params={"fields": "user_id,username", "access_token": token},
        timeout=60,
    )
    if response.status_code >= 400:
        raise KtwError(
            f"Instagram validation failed: HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )
    data = response.json()
    resolved_id = data.get("user_id") or data.get("id")
    print(f"OK Instagram token validated ({base})")
    print(f"OK Instagram account: @{data.get('username')} (user_id={resolved_id})")
    if configured_id and not str(configured_id).strip().isdigit():
        print(
            f"NOTE INSTAGRAM_USER_ID is {configured_id!r}; set it to the numeric "
            f"id {resolved_id} (or leave it and it will be auto-resolved)."
        )


def validate_rclone(remote_root):
    require_present("RCLONE_CONFIG")
    configure_rclone_from_secret()
    rclone_bin = rclone_bin_from_env()
    command = [rclone_bin, "lsd", remote_root]
    print(f"Checking rclone remote: {remote_root}")
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as e:
        raise KtwError(
            "rclone was not found. Install rclone or set KBP_RCLONE_BIN."
        ) from e
    except subprocess.CalledProcessError as e:
        raise KtwError(f"rclone validation failed for {remote_root}") from e
    print("OK RCLONE_CONFIG validated with rclone")


def main(argv=None):
    load_dotenv_if_present()
    parser = argparse.ArgumentParser(
        description="Validate Know the Big Picture secrets without rendering or uploading."
    )
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--gemini", action="store_true")
    parser.add_argument("--openai", action="store_true")
    parser.add_argument("--youtube", action="store_true")
    parser.add_argument("--instagram", action="store_true")
    parser.add_argument("--rclone", action="store_true")
    parser.add_argument(
        "--remote-root",
        default=os.environ.get("KBP_REMOTE_ROOT", "gdrive:knowthebigpicture"),
    )
    args = parser.parse_args(argv)

    if not any(
        [args.all, args.gemini, args.openai, args.youtube, args.instagram, args.rclone]
    ):
        args.gemini = True
        args.youtube = True

    try:
        if args.all or args.gemini:
            validate_gemini()
        if args.all or args.openai:
            validate_openai()
        if args.all or args.youtube:
            validate_youtube()
        if args.all or args.instagram:
            validate_instagram()
        if args.all or args.rclone:
            validate_rclone(args.remote_root)
    except KtwError as e:
        print(f"ERROR: {e}")
        return 1

    print("DONE secrets validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
