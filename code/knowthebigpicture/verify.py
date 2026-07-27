import json
import re

from .errors import VerificationError
from .job import parse_settings
from .parse import sanitize_source
from . import settings


def normalize(text):
    return re.sub(r"\s+", " ", (text or "")).strip().casefold()


def word_count(text):
    return len((text or "").split())


def quote_match(quote, source_norm, source_raw):
    if quote in source_raw:
        return "exact"
    if normalize(quote) and normalize(quote) in source_norm:
        return "normalized"
    return None


def verify_slide(slide, source_norm, source_raw, cfg):
    heading = slide.get("heading", "")
    explanation = slide.get("explanation", "")
    result = {"passed": True, "checks": {}}

    def check(name, passed, reason=None, **extra):
        result["checks"][name] = {"passed": passed, **extra}
        if reason:
            result["checks"][name]["reason"] = reason
        if not passed:
            result["passed"] = False

    heading_words = word_count(heading)
    explanation_words = word_count(explanation)
    check(
        "heading_word_cap",
        0 < heading_words <= cfg["max_words_per_heading"],
        f"heading has {heading_words} words (max {cfg['max_words_per_heading']})",
        word_count=heading_words,
    )
    check(
        "explanation_word_cap",
        0 < explanation_words <= cfg["max_words_per_explanation"],
        f"explanation has {explanation_words} words "
        f"(max {cfg['max_words_per_explanation']})",
        word_count=explanation_words,
    )
    quotes = slide.get("source_quotes") or []
    matches = [quote_match(q, source_norm, source_raw) for q in quotes]
    grounded = bool(quotes) and all(matches)
    check(
        "source_grounding",
        grounded,
        "every slide needs source_quotes found verbatim in source.txt",
        matches=matches,
    )
    check(
        "image_prompt",
        bool((slide.get("image_prompt") or "").strip()),
        "image_prompt is required",
    )
    slide["verification"] = result
    return result["passed"]


def verify_structure(explainer, cfg):
    slides = explainer.get("slides", [])
    problems = []
    if not cfg["min_slides"] <= len(slides) <= cfg["max_slides"]:
        problems.append(
            f"expected {cfg['min_slides']}-{cfg['max_slides']} slides, found {len(slides)}"
        )
    if not slides or slides[0].get("role") != settings.ROLE_QUESTION:
        problems.append("the first slide must have role 'question'")
    if sum(s.get("role") == settings.ROLE_QUESTION for s in slides) != 1:
        problems.append("expected exactly one question slide")
    question = explainer.get("explainer", {}).get("question", "")
    if slides and normalize(slides[0].get("heading")) != normalize(question):
        problems.append("the first slide heading must exactly match the central question")
    ids = [s.get("id") for s in slides]
    if ids != list(range(1, len(slides) + 1)):
        problems.append("slide ids must be sequential starting at 1")
    if len({normalize(s.get("heading")) for s in slides}) != len(slides):
        problems.append("slide headings must not be duplicated")
    return problems


def run_verify(job, explainer):
    """Stage 2: verify structure and source grounding; write results in place."""
    cfg = parse_settings(job)
    source_raw = sanitize_source(job.source_path.read_text())
    source_norm = normalize(source_raw)
    slides = explainer.get("slides", [])
    failed = [
        slide.get("id")
        for slide in slides
        if not verify_slide(slide, source_norm, source_raw, cfg)
    ]
    structure_problems = verify_structure(explainer, cfg)
    ok = not failed and not structure_problems
    explainer["verification_summary"] = {
        "status": "passed" if ok else "failed",
        "slides_total": len(slides),
        "slides_passed": len(slides) - len(failed),
        "slides_failed": len(failed),
        "failed_slides": failed,
        "structure_problems": structure_problems,
        "grounding": "all_slides",
    }
    job.explainer_path.write_text(json.dumps(explainer, indent=2) + "\n")
    if ok:
        print(f"Verification passed: {len(slides)}/{len(slides)} slides")
        return explainer
    print("Verification FAILED:")
    for problem in structure_problems:
        print(f"  - {problem}")
    if failed:
        print(f"  - failing slides: {failed}")
    if cfg["on_verification_fail"] == "fail_job":
        raise VerificationError(
            f"Explainer failed verification. See {job.explainer_path}."
        )
    return explainer
