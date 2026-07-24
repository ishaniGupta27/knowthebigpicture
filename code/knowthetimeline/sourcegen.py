from .errors import KttError
from .job import parse_settings
from .parse import extract_response_text
from .secrets import secret_value
from . import settings

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

SOURCE_MARKER = "TOPIC / ARTICLE:"


def load_source_prompt():
    """Return the instruction portion of source_prompt.txt (without the
    human-facing 'TOPIC / ARTICLE:' paste block)."""
    path = settings.PROMPTS_DIR / "source_prompt.txt"
    text = path.read_text()
    marker_index = text.find(SOURCE_MARKER)
    if marker_index != -1:
        text = text[:marker_index]
    return text.strip()


def strip_code_fences(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        for lang in ("text", "plaintext", "markdown", "md"):
            if text.lower().startswith(lang):
                text = text[len(lang):].strip()
                break
    return text.strip()


def call_openai_text(system_prompt, user_message, model, api_key):
    import requests

    response = requests.post(
        OPENAI_RESPONSES_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        },
        timeout=180,
    )

    if response.status_code >= 400:
        raise KttError(
            f"OpenAI source request failed: HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    text = extract_response_text(response.json())
    if not text:
        raise KttError("OpenAI source response did not contain text")
    return strip_code_fences(text)


def ensure_source(job, dry_run=False):
    """Step 0: guarantee inputs/source.txt exists.

    - source.txt present -> use it (no LLM call).
    - only headline.txt present -> generate source.txt from it (one LLM call).
    - neither present -> error.
    """
    if job.source_path.is_file() and job.source_path.read_text().strip():
        print(f"SKIP step 0; source already exists: {job.source_path}")
        return

    if not job.headline_path.is_file():
        raise KttError(
            "Provide inputs/source.txt or inputs/headline.txt "
            f"under {job.inputs_dir}."
        )

    headline = job.headline_path.read_text().strip()
    if not headline:
        raise KttError(f"Headline file is empty: {job.headline_path}")

    if dry_run:
        raise KttError(
            "Source generation (step 0) needs a real run. Either run without "
            "--dry-run, or provide inputs/source.txt for the dry run."
        )

    cfg = parse_settings(job)
    api_key = secret_value("OPENAI_API_KEY", required=True)
    model = secret_value("OPENAI_MODEL") or cfg["model"]

    print(f"Generating source from headline with OpenAI model: {model}")
    source_text = call_openai_text(
        load_source_prompt(),
        f"{SOURCE_MARKER}\n{headline}",
        model,
        api_key,
    )

    job.source_path.parent.mkdir(parents=True, exist_ok=True)
    job.source_path.write_text(source_text + "\n")
    print(f"Source written: {job.source_path}")
