import re

from .job import parse_settings, story_overrides
from .images import make_neutral_background
from .job import image_settings
from .parse import write_json
from . import settings
from .status import utc_now


def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if len(p.split()) >= 3]


def first_words(text, n=settings.MAX_WORDS_PER_HEADLINE):
    words = text.split()
    return " ".join(words[:n])


MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}

# Optional connective ("in"/"on"/"by"/"since") + a "Month YYYY" or bare "YYYY".
DATE_RE = re.compile(
    r"\b(?:in|on|by|since)\s+"
    r"((?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+\d{4}|\d{4})\b"
    r"|\b((?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+\d{4}|\d{4})\b",
    re.IGNORECASE,
)


def extract_date(sentence):
    """Pull the first date out of a sentence: (iso, display, cleaned_sentence)."""
    match = DATE_RE.search(sentence)
    if not match:
        return None, None, sentence

    display = (match.group(1) or match.group(2)).strip()
    parts = display.split()
    if len(parts) == 2:
        iso = f"{parts[1]}-{MONTHS[parts[0].lower()]}"
        display = f"{parts[0].title()} {parts[1]}"
    else:
        iso = display  # bare year

    cleaned = (sentence[: match.start()] + sentence[match.end():])
    cleaned = re.sub(r"\s*,\s*,", ",", cleaned)
    cleaned = re.sub(r"\s+,", ",", cleaned)
    cleaned = re.sub(r"\s+\.", ".", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip().strip(",").strip()
    return iso, display, cleaned


def mock_scene(sentence):
    return (
        "A quiet, evocative documentary scene that symbolizes the moment described, "
        "with atmospheric lighting and no readable text."
    )


def mock_parse(job, force=False):
    """Offline Stage 1: build a valid timeline from real source sentences."""
    if job.timeline_path.is_file() and not force:
        import json

        with job.timeline_path.open("r") as f:
            return json.load(f)

    cfg = parse_settings(job)
    overrides = story_overrides(job)
    text = job.source_path.read_text()
    sentences = split_sentences(text)

    hook_sentence = sentences[0] if sentences else "How did we get here?"
    dated = []
    for sentence in sentences[1:]:
        iso, display, cleaned = extract_date(sentence)
        if iso:
            dated.append({"iso": iso, "display": display, "cleaned": cleaned,
                          "sentence": sentence})

    # Real parsing orders events oldest-first; mirror that so Stage 2's
    # chronology check passes on mocked data too.
    dated.sort(key=lambda d: d["iso"])

    # If the source is thin on dates, top up with undated sentences (they carry
    # no kicker and are skipped by the chronology check).
    needed = cfg["min_developments"] + 2  # starting_point + devs + resolution
    if len(dated) < needed:
        for sentence in sentences[1:]:
            iso, display, cleaned = extract_date(sentence)
            if iso:
                continue
            dated.append({"iso": None, "display": None, "cleaned": cleaned,
                          "sentence": sentence})
            if len(dated) >= needed:
                break

    # Trim the middle to respect max_developments (keep starting_point + resolution).
    max_dev = cfg["max_developments"]
    if len(dated) - 2 > max_dev:
        keep_head = dated[: 1 + max_dev]
        dated = keep_head + [dated[-1]]

    def make_node(node_id, role, headline, source_quote, iso=None, display=None,
                  subtitle=None, priority=None):
        node = {
            "id": node_id,
            "role": role,
            "subtitle": subtitle,
            "headline": first_words(headline),
            "event_date": iso,
            "event_date_display": display,
            "source_quote": source_quote,
            "image_prompt": mock_scene(source_quote),
        }
        if priority is not None:
            node["priority"] = priority
        return node

    nodes = []
    _, _, hook_clean = extract_date(hook_sentence)
    nodes.append(make_node(1, settings.ROLE_PRESENT_HOOK, hook_clean, hook_sentence))

    for offset, item in enumerate(dated):
        node_id = len(nodes) + 1
        if offset == 0:
            role = settings.ROLE_STARTING_POINT
            subtitle = "To understand how, we have to go back."
            priority = None
        elif offset == len(dated) - 1:
            role = settings.ROLE_RESOLUTION
            subtitle = None
            priority = None
        else:
            role = settings.ROLE_DEVELOPMENT
            subtitle = None
            priority = (offset % 3) + 1
        nodes.append(
            make_node(
                node_id, role, item["cleaned"], item["sentence"],
                iso=item["iso"], display=item["display"],
                subtitle=subtitle, priority=priority,
            )
        )

    timeline = {
        "schema_version": 2,
        "story": {
            "id": job.job_id,
            "topic": overrides["topic"] or first_words(text, 6) or "Dry Run Timeline",
            "topic_source": "author" if overrides["topic"] else "mock",
            "central_question": overrides["central_question"] or "How did we get here?",
            "question_source": "author" if overrides["central_question"] else "mock",
        },
        "nodes": nodes,
    }

    metadata = {
        "title": f"{timeline['story']['topic']}: How did we get here?"[:100],
        "description": [
            "A 60-second chronological breakdown of how this story unfolded.",
            "",
            "#Shorts",
        ],
        "tags": ["timeline", "explained", "news", "how did we get here"],
        "generated_at": utc_now(),
        "source": "dry_run",
    }

    write_json(job.timeline_path, timeline)
    write_json(job.metadata_path, metadata)
    print(f"[dry-run] mock timeline written: {len(nodes)} nodes")
    return timeline


def mock_images(job, timeline):
    """Offline Stage 3: neutral backgrounds instead of API calls."""
    cfg = image_settings(job)
    job.backgrounds_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for node in timeline.get("nodes", []):
        path = job.backgrounds_dir / f"{node['id']}.jpg"
        if not path.is_file():
            make_neutral_background(path, cfg["size"])
        results.append({"id": node["id"], "status": "mock"})
    print(f"[dry-run] mock backgrounds: {len(results)}")
    return results
