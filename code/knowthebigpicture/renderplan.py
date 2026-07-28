import json

from .job import video_settings
from . import settings


def word_count(text):
    return len((text or "").split())


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def natural_duration(slide, content_format):
    words = word_count(slide.get("heading")) + word_count(slide.get("explanation"))
    profile = (
        settings.TITLE_TIMING_PROFILE
        if slide.get("role") == settings.ROLE_QUESTION
        else settings.TIMING_PROFILES.get(
            content_format, settings.TIMING_PROFILES[settings.DEFAULT_CONTENT_FORMAT]
        )
    )
    duration = clamp(
        profile["base"] + words * profile["per_word"],
        profile["min"],
        profile["max"],
    )
    if slide.get("role") == settings.ROLE_SURPRISING_FACT:
        duration += settings.TIMING_FINAL_BONUS
    if (
        content_format == settings.FORMAT_MYTH_VS_FACT
        and slide.get("role") == settings.ROLE_MISCONCEPTION
    ):
        duration += settings.MYTH_VERDICT_BONUS
    return duration


def select_slides(slides, durations, outro_duration, video_cfg):
    kept = list(slides)

    def total():
        return sum(durations[s["id"]] for s in kept) + outro_duration

    while total() > video_cfg["max_seconds"]:
        optional = [s for s in kept if s.get("priority", 2) > 1]
        if not optional:
            break
        drop = max(optional, key=lambda s: (s.get("priority", 2), -s["id"]))
        kept = [s for s in kept if s["id"] != drop["id"]]
    return kept


def scale_to_range(kept, durations, outro_duration, cfg):
    content = sum(durations[s["id"]] for s in kept)
    total = content + outro_duration
    if total > cfg["max_seconds"] and content:
        return (cfg["max_seconds"] - outro_duration) / content
    if total < cfg["min_seconds"] and content:
        return (cfg["min_seconds"] - outro_duration) / content
    return 1.0


def build_render_plan(job, explainer):
    video_cfg = video_settings(job)
    source_slides = explainer.get("slides", [])
    content_format = explainer.get("explainer", {}).get(
        "content_format", settings.DEFAULT_CONTENT_FORMAT
    )
    outro_duration = (
        settings.DEFAULT_OUTRO_DURATION if video_cfg["outro_enabled"] else 0.0
    )
    durations = {
        slide["id"]: natural_duration(slide, content_format)
        for slide in source_slides
    }
    kept = select_slides(source_slides, durations, outro_duration, video_cfg)
    scale = scale_to_range(kept, durations, outro_duration, video_cfg)

    slides = []
    cursor = 0.0
    for slide in kept:
        duration = round(durations[slide["id"]] * scale, 2)
        slides.append(
            {
                "id": slide["id"],
                "role": slide["role"],
                "word_count": (
                    word_count(slide.get("heading"))
                    + word_count(slide.get("explanation"))
                ),
                "start": round(cursor, 2),
                "end": round(cursor + duration, 2),
                "duration": duration,
            }
        )
        cursor += duration
    # Per-slide rounding can otherwise put the final plan a hundredth of a
    # second above the configured cap. Absorb that rounding only in the last
    # content slide.
    max_content_duration = video_cfg["max_seconds"] - outro_duration
    if slides and cursor > max_content_duration:
        overflow = round(cursor - max_content_duration, 2)
        slides[-1]["duration"] = round(slides[-1]["duration"] - overflow, 2)
        slides[-1]["end"] = round(slides[-1]["end"] - overflow, 2)
        cursor -= overflow
    if outro_duration:
        slides.append(
            {
                "id": "outro",
                "role": "outro",
                "start": round(cursor, 2),
                "end": round(cursor + outro_duration, 2),
                "duration": outro_duration,
            }
        )
        cursor += outro_duration

    kept_ids = {slide["id"] for slide in kept}
    plan = {
        "generated_from": "explainer.json",
        "params": {
            "content_format": content_format,
            "timing_profile": settings.TIMING_PROFILES.get(content_format),
            "title_timing_profile": settings.TITLE_TIMING_PROFILE,
            "min_seconds": video_cfg["min_seconds"],
            "max_seconds": video_cfg["max_seconds"],
            "scale_applied": round(scale, 3),
        },
        "dropped_slides": [
            slide["id"] for slide in source_slides if slide["id"] not in kept_ids
        ],
        "slides": slides,
        "total_duration": round(cursor, 2),
    }
    job.render_plan_path.parent.mkdir(parents=True, exist_ok=True)
    job.render_plan_path.write_text(json.dumps(plan, indent=2) + "\n")
    print(f"Render plan: {len(slides)} slides, {plan['total_duration']}s total")
    if plan["dropped_slides"]:
        print(f"  dropped optional slides: {plan['dropped_slides']}")
    return plan
