import json
import re

from .errors import InsufficientSourceError, KttError
from .job import parse_settings, story_overrides
from .secrets import secret_value
from . import settings
from .status import utc_now

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

# Markdown link [label](url) -> label, and bare citation markers like [1, 2, 3].
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_CITATION_RE = re.compile(r"\[\d+(?:\s*,\s*\d+)*\]")


def sanitize_source(text):
    """Strip pasted markdown/citation junk so quotes stay clean and verifiable.

    Applied identically before parsing and before verification so the LLM's
    verbatim source_quote reliably matches the source it was given.
    """
    text = _MD_LINK_RE.sub(r"\1", text)
    text = _CITATION_RE.sub("", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text


def load_system_prompt():
    path = settings.PROMPTS_DIR / "parse_system_prompt.txt"
    return path.read_text()


def read_source(job):
    text = sanitize_source(job.source_path.read_text())
    if not text.strip():
        raise KttError(f"Source file is empty: {job.source_path}")
    return text


def build_user_message(job, cfg, source_text):
    overrides = story_overrides(job)
    return (
        "AUTHOR OVERRIDES (may be empty):\n"
        f"topic: {overrides['topic'] or ''}\n"
        f"central_question: {overrides['central_question'] or ''}\n"
        f"MIN developments: {cfg['min_developments']}\n"
        f"MAX developments: {cfg['max_developments']}\n\n"
        "SOURCE DOCUMENT:\n"
        f"{source_text}"
    )


def extract_response_text(response_json):
    if response_json.get("output_text"):
        return response_json["output_text"]

    chunks = []
    for item in response_json.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                chunks.append(text)
    return "\n".join(chunks).strip()


def parse_json_text(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.startswith("json"):
            text = text[len("json"):].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise KttError(f"Parse stage returned invalid JSON: {e}") from e


def call_openai(system_prompt, user_message, model, api_key):
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
            f"OpenAI parse request failed: HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    text = extract_response_text(response.json())
    if not text:
        raise KttError("OpenAI parse response did not contain text")
    return parse_json_text(text)


def normalize_nodes(raw_nodes):
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise KttError("Parse output must contain a non-empty 'nodes' list")

    nodes = []
    for index, raw in enumerate(raw_nodes, start=1):
        if not isinstance(raw, dict):
            raise KttError("Each node must be an object")
        role = raw.get("role")
        if role not in settings.VALID_ROLES:
            raise KttError(f"Node {index} has invalid role: {role}")

        node = {
            "id": index,
            "role": role,
            "subtitle": raw.get("subtitle"),
            "headline": (raw.get("headline") or "").strip(),
            "detail": (raw.get("detail") or "").strip() or None,
            "event_date": raw.get("event_date"),
            "event_date_display": raw.get("event_date_display"),
            "source_quote": raw.get("source_quote"),
            "image_prompt": raw.get("image_prompt"),
        }
        if role == settings.ROLE_DEVELOPMENT:
            node["priority"] = int(raw.get("priority", 2))
        nodes.append(node)
    return nodes


def build_timeline(job, cfg, parsed):
    overrides = story_overrides(job)

    author_topic = overrides["topic"]
    author_question = overrides["central_question"]

    topic = author_topic or parsed.get("topic")
    question = author_question or parsed.get("central_question")
    if not topic:
        raise KttError("Parse output missing 'topic'")
    if not question:
        raise KttError("Parse output missing 'central_question'")

    return {
        "schema_version": 2,
        "story": {
            "id": job.job_id,
            "topic": topic,
            "topic_source": "author" if author_topic else "llm",
            "central_question": question,
            "question_source": "author" if author_question else "llm",
        },
        "nodes": normalize_nodes(parsed.get("nodes")),
    }


def build_metadata(parsed):
    youtube = parsed.get("youtube", {})
    if not isinstance(youtube, dict):
        raise KttError("Parse output 'youtube' must be an object")

    return {
        "title": (youtube.get("title") or "").strip(),
        "description": youtube.get("description") or [],
        "tags": youtube.get("tags") or [],
        "generated_at": utc_now(),
        "source": "parse",
    }


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def run_parse(job, force=False):
    """Stage 1: source.txt -> timeline.json + youtube_metadata.json (one call)."""
    if job.timeline_path.is_file() and not force:
        print(f"SKIP parse; timeline already exists: {job.timeline_path}")
        with job.timeline_path.open("r") as f:
            return json.load(f)

    cfg = parse_settings(job)
    source_text = read_source(job)
    api_key = secret_value("OPENAI_API_KEY", required=True)
    model = secret_value("OPENAI_MODEL") or cfg["model"]

    print(f"Parsing source with OpenAI model: {model}")
    parsed = call_openai(
        load_system_prompt(),
        build_user_message(job, cfg, source_text),
        model,
        api_key,
    )

    if isinstance(parsed, dict) and parsed.get("error") == "insufficient_source":
        reason = parsed.get("reason", "source lacked enough dated facts")
        raise InsufficientSourceError(f"Source is insufficient for a timeline: {reason}")

    timeline = build_timeline(job, cfg, parsed)
    metadata = build_metadata(parsed)

    write_json(job.timeline_path, timeline)
    write_json(job.metadata_path, metadata)

    print(f"Timeline written: {job.timeline_path}")
    print(f"Topic: {timeline['story']['topic']}")
    print(f"Nodes: {len(timeline['nodes'])}")
    print(f"Metadata written: {job.metadata_path}")
    return timeline
