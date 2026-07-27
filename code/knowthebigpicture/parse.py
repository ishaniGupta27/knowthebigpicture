import json
import re

from .errors import InsufficientSourceError, KtwError
from .job import explainer_overrides, parse_settings
from .secrets import secret_value
from . import settings
from .status import utc_now

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_CITATION_RE = re.compile(r"\[\d+(?:\s*,\s*\d+)*\]")


def sanitize_source(text):
    text = _MD_LINK_RE.sub(r"\1", text)
    text = _CITATION_RE.sub("", text)
    return re.sub(r"[ \t]{2,}", " ", text)


def load_system_prompt():
    return (settings.PROMPTS_DIR / "parse_system_prompt.txt").read_text()


def read_source(job):
    text = sanitize_source(job.source_path.read_text())
    if not text.strip():
        raise KtwError(f"Source file is empty: {job.source_path}")
    return text


def read_question(job):
    override = explainer_overrides(job)["question"]
    if override:
        return override.strip()
    if job.question_path.is_file():
        question = job.question_path.read_text().strip()
        if question:
            return question
    raise KtwError("The explainer needs a non-empty question")


def build_user_message(job, cfg, question, source_text):
    overrides = explainer_overrides(job)
    return (
        "EXPLAINER REQUEST\n"
        f"question: {question}\n"
        f"subject override: {overrides['subject'] or ''}\n"
        f"audience: {overrides['audience']}\n"
        f"minimum slides: {cfg['min_slides']}\n"
        f"maximum slides: {cfg['max_slides']}\n"
        f"maximum heading words: {cfg['max_words_per_heading']}\n"
        f"maximum explanation words: {cfg['max_words_per_explanation']}\n\n"
        "SOURCE PACKET\n"
        f"{source_text}"
    )


def extract_response_text(response_json):
    if response_json.get("output_text"):
        return response_json["output_text"]
    chunks = []
    for item in response_json.get("output", []):
        for content in item.get("content", []):
            if content.get("text"):
                chunks.append(content["text"])
    return "\n".join(chunks).strip()


def parse_json_text(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise KtwError(f"Generation stage returned invalid JSON: {exc}") from exc


def call_openai(system_prompt, user_message, model, api_key):
    import requests

    response = requests.post(
        OPENAI_RESPONSES_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
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
            f"OpenAI explainer request failed: HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )
    text = extract_response_text(response.json())
    if not text:
        raise KtwError("OpenAI response did not contain text")
    return parse_json_text(text)


def normalize_slides(raw_slides):
    if not isinstance(raw_slides, list) or not raw_slides:
        raise KtwError("Generation output must contain a non-empty 'slides' list")
    slides = []
    for index, raw in enumerate(raw_slides, 1):
        if not isinstance(raw, dict):
            raise KtwError("Each slide must be an object")
        role = raw.get("role")
        if role not in settings.VALID_ROLES:
            raise KtwError(f"Slide {index} has invalid role: {role}")
        quotes = raw.get("source_quotes") or []
        if isinstance(quotes, str):
            quotes = [quotes]
        slides.append(
            {
                "id": index,
                "role": role,
                "heading": (raw.get("heading") or "").strip(),
                "explanation": (raw.get("explanation") or "").strip(),
                "source_quotes": quotes,
                "image_prompt": (raw.get("image_prompt") or "").strip(),
                "priority": int(raw.get("priority", 1 if role == "question" else 2)),
            }
        )
    return slides


def build_explainer(job, parsed, question):
    overrides = explainer_overrides(job)
    subject = overrides["subject"] or parsed.get("subject")
    summary = parsed.get("summary")
    if not subject or not summary:
        raise KtwError("Generation output must include 'subject' and 'summary'")
    return {
        "schema_version": 1,
        "explainer": {
            "id": job.job_id,
            "question": question,
            "question_source": (
                "author" if overrides["question"] or job.question_path.is_file() else "generated"
            ),
            "subject": subject,
            "subject_source": "author" if overrides["subject"] else "llm",
            "audience": overrides["audience"],
            "summary": summary,
        },
        "slides": normalize_slides(parsed.get("slides")),
    }


def build_metadata(parsed):
    youtube = parsed.get("youtube", {})
    if not isinstance(youtube, dict):
        raise KtwError("Generation output 'youtube' must be an object")
    return {
        "title": (youtube.get("title") or "").strip(),
        "description": youtube.get("description") or [],
        "tags": youtube.get("tags") or [],
        "generated_at": utc_now(),
        "source": "explainer_generation",
    }


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def run_parse(job, force=False):
    """Stage 1: question + source -> explainer.json and publishing metadata."""
    if job.explainer_path.is_file() and not force:
        print(f"SKIP generation; explainer already exists: {job.explainer_path}")
        return json.loads(job.explainer_path.read_text())

    cfg = parse_settings(job)
    question = read_question(job)
    source_text = read_source(job)
    model = secret_value("OPENAI_MODEL") or cfg["model"]
    print(f"Creating explainer with OpenAI model: {model}")
    parsed = call_openai(
        load_system_prompt(),
        build_user_message(job, cfg, question, source_text),
        model,
        secret_value("OPENAI_API_KEY", required=True),
    )
    if isinstance(parsed, dict) and parsed.get("error") == "insufficient_source":
        raise InsufficientSourceError(
            parsed.get("reason", "the source cannot support a grounded explanation")
        )

    explainer = build_explainer(job, parsed, question)
    write_json(job.explainer_path, explainer)
    write_json(job.metadata_path, build_metadata(parsed))
    print(f"Explainer written: {job.explainer_path}")
    print(f"Question: {question}")
    print(f"Slides: {len(explainer['slides'])}")
    return explainer
