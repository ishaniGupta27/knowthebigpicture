import json
import re

from .job import explainer_overrides, image_settings, parse_settings
from .images import make_neutral_background
from .parse import read_question, sanitize_source, write_json
from . import settings
from .status import utc_now


def split_sentences(text):
    return [
        part.strip()
        for part in re.split(r"(?<=[.!?])\s+", text.strip())
        if len(part.split()) >= 3
    ]


def first_words(text, limit):
    return " ".join((text or "").split()[:limit]).strip()


def mock_parse(job, force=False):
    """Offline Stage 1: make a structurally valid explainer from source sentences."""
    if job.explainer_path.is_file() and not force:
        return json.loads(job.explainer_path.read_text())

    cfg = parse_settings(job)
    overrides = explainer_overrides(job)
    question = read_question(job)
    source = sanitize_source(job.source_path.read_text())
    sentences = split_sentences(source)
    if not sentences:
        sentences = [source.strip()]

    count = min(cfg["max_slides"], max(cfg["min_slides"], len(sentences)))
    selected = [sentences[index % len(sentences)] for index in range(count)]
    role_sequence = [
        settings.ROLE_QUESTION,
        settings.ROLE_DEFINITION,
        settings.ROLE_PURPOSE,
        settings.ROLE_MECHANISM,
        settings.ROLE_EXAMPLE,
        settings.ROLE_MISCONCEPTION,
        settings.ROLE_SURPRISING_FACT,
    ]
    slides = []
    for index, sentence in enumerate(selected, 1):
        role = (
            settings.ROLE_QUESTION
            if index == 1
            else (
                settings.ROLE_TYPE
                if overrides["content_format"] == settings.FORMAT_TYPES
                else role_sequence[min(index - 1, len(role_sequence) - 1)]
            )
        )
        heading = (
            question
            if index == 1
            else first_words(sentence, cfg["max_words_per_heading"])
        )
        slides.append(
            {
                "id": index,
                "role": role,
                "heading": heading,
                "explanation": first_words(
                    sentence, cfg["max_words_per_explanation"]
                ),
                "source_quotes": [sentence],
                "image_prompt": (
                    "A clear educational visualization of the idea using a concrete "
                    "object, process, or cutaway, with no readable text."
                ),
                "priority": (
                    1
                    if overrides["content_format"] == settings.FORMAT_TYPES
                    else (1 if index <= 4 else (2 if index == count else 3))
                ),
            }
        )

    subject = overrides["subject"] or first_words(question.rstrip("?"), 6)
    explainer = {
        "schema_version": 1,
        "explainer": {
            "id": job.job_id,
            "question": question,
            "question_source": "author",
            "subject": subject,
            "subject_source": "author" if overrides["subject"] else "mock",
            "audience": overrides["audience"],
            "content_format": overrides["content_format"],
            "item_count": (
                overrides["item_count"]
                if overrides["content_format"] == settings.FORMAT_TYPES
                else None
            ),
            "summary": first_words(sentences[0], cfg["max_words_per_explanation"]),
        },
        "slides": slides,
    }
    metadata = {
        "title": question[:100],
        "description": ["A plain-language explanation of the question.", "", "#Shorts"],
        "tags": [subject.lower(), "explained", "how it works"],
        "generated_at": utc_now(),
        "source": "dry_run",
    }
    write_json(job.explainer_path, explainer)
    write_json(job.metadata_path, metadata)
    print(f"[dry-run] mock explainer written: {len(slides)} slides")
    return explainer


def mock_images(job, explainer, force=False):
    cfg = image_settings(job)
    job.backgrounds_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for slide in explainer.get("slides", []):
        path = job.backgrounds_dir / f"{slide['id']}.jpg"
        if force or not path.is_file():
            make_neutral_background(path, cfg["size"])
        results.append({"id": slide["id"], "status": "mock"})
    print(f"[dry-run] mock backgrounds: {len(results)}")
    return results
