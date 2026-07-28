from .errors import KtwError
from .job import explainer_overrides, parse_settings
from .parse import extract_response_text
from .secrets import secret_value
from . import settings

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

SOURCE_MARKER = "QUESTION:"


def mock_source_for_question(
    question,
    content_format=settings.DEFAULT_CONTENT_FORMAT,
    item_count=settings.DEFAULT_TYPES_ITEM_COUNT,
):
    """Create an offline source packet that exercises the dry-run pipeline.

    The statements are intentionally generic: dry-run validates plumbing and
    layout, not factual research or editorial quality.
    """
    topic = question.rstrip().rstrip("?").strip() or "the question"
    statements = [f"This mock source packet is about the question: {question}."]
    if content_format == settings.FORMAT_TYPES:
        statements.extend(
            f"Mock variety {index} is a distinct placeholder example for {topic}."
            for index in range(1, item_count + 1)
        )
    else:
        statements.extend(
            [
                f"The subject being explained in this offline test is {topic}.",
                f"A complete real run would research reliable facts about {topic}.",
                f"The explanation would then organize those facts into a clear teaching sequence about {topic}.",
                f"Each slide would use a source quotation supporting its explanation of {topic}.",
                f"This placeholder material exists only to test generation, verification, composition, and rendering for {topic}.",
            ]
        )
    return "\n".join(statements)


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
        raise KtwError(
            f"OpenAI source request failed: HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    text = extract_response_text(response.json())
    if not text:
        raise KtwError("OpenAI source response did not contain text")
    return strip_code_fences(text)


def call_gemini_text(system_prompt, user_message, model, api_key, temperature):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    config_kwargs = {"system_instruction": system_prompt}
    if settings.gemini_supports_temperature(model):
        config_kwargs["temperature"] = temperature
    response = client.models.generate_content(
        model=model,
        contents=user_message,
        config=types.GenerateContentConfig(**config_kwargs),
    )
    text = getattr(response, "text", None)
    if not text:
        raise KtwError("Gemini source response did not contain text")
    return strip_code_fences(text)


def generate_source_text(system_prompt, user_message, cfg):
    """Generate the source packet with the job's configured provider.

    Gemini is the default. There is no automatic cross-provider fallback: set
    parse.provider to "openai" explicitly to use OpenAI.
    """
    provider = cfg["provider"]
    if provider == "gemini":
        api_key = secret_value("GEMINI_API_KEY") or secret_value("GOOGLE_API_KEY")
        if not api_key:
            raise KtwError("GEMINI_API_KEY is not set")
        model = secret_value("GEMINI_MODEL") or cfg["gemini_model"]
        print(f"Generating source packet from question with Gemini model: {model}")
        return call_gemini_text(
            system_prompt, user_message, model, api_key, cfg["temperature"]
        )
    if provider == "openai":
        api_key = secret_value("OPENAI_API_KEY", required=True)
        model = secret_value("OPENAI_MODEL") or cfg["model"]
        print(f"Generating source packet from question with OpenAI model: {model}")
        return call_openai_text(system_prompt, user_message, model, api_key)
    raise KtwError(f"Unknown LLM provider: {provider}")


def ensure_source(job, dry_run=False):
    """Stage 0: create a reusable source packet when only a question is supplied."""
    if job.source_path.is_file() and job.source_path.read_text().strip():
        print(f"SKIP step 0; source already exists: {job.source_path}")
        return

    if not job.question_path.is_file():
        raise KtwError(
            "Provide inputs/question.txt, with optional inputs/source.txt, "
            f"under {job.inputs_dir}."
        )

    question = job.question_path.read_text().strip()
    if not question:
        raise KtwError(f"Question file is empty: {job.question_path}")

    if dry_run:
        overrides = explainer_overrides(job)
        source_text = mock_source_for_question(
            question,
            content_format=overrides["content_format"],
            item_count=overrides["item_count"],
        )
        job.source_path.parent.mkdir(parents=True, exist_ok=True)
        job.source_path.write_text(source_text + "\n")
        print(f"[dry-run] mock source written: {job.source_path}")
        return

    cfg = parse_settings(job)
    source_text = generate_source_text(
        load_source_prompt(),
        (
            f"CONTENT FORMAT: {explainer_overrides(job)['content_format']}\n"
            f"REQUESTED ITEMS: {explainer_overrides(job)['item_count']}\n"
            f"{SOURCE_MARKER}\n{question}"
        ),
        cfg,
    )

    job.source_path.parent.mkdir(parents=True, exist_ok=True)
    job.source_path.write_text(source_text + "\n")
    print(f"Source written: {job.source_path}")
