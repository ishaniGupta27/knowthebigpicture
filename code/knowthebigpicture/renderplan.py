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


def _speech_duration(narration, slide_id):
    entry = (narration or {}).get("slides", {}).get(str(slide_id))
    return float(entry["duration"]) if entry else 0.0


def _voiced_duration(read_floor, speech, pad, speed):
    """Slide time: long enough to read the text AND speak the line."""
    if speech <= 0:
        return read_floor
    return max(read_floor, pad + speech / speed)


def _plan_total(kept, reads, speeches, pad, speed, outro_duration):
    return (
        sum(
            _voiced_duration(reads[s["id"]], speeches[s["id"]], pad, speed)
            for s in kept
        )
        + outro_duration
    )


def _fit_speed(kept, reads, speeches, pad, outro_duration, max_seconds):
    speed = 1.0
    while speed < settings.ATEMPO_MAX - 1e-9:
        speed = round(speed + 0.01, 2)
        if _plan_total(kept, reads, speeches, pad, speed, outro_duration) <= max_seconds:
            return speed
    return settings.ATEMPO_MAX


def build_narration_timing(source_slides, reads, speeches, outro_duration, video_cfg):
    """Tiered fit: drop optional slides -> trim padding -> compress speech."""
    full_pad = settings.NARRATION_LEAD_IN + settings.NARRATION_TAIL_PAD
    floor_pad = settings.NARRATION_LEAD_IN_FLOOR + settings.NARRATION_TAIL_PAD_FLOOR
    max_seconds = video_cfg["max_seconds"]

    durations_full = {
        s["id"]: _voiced_duration(reads[s["id"]], speeches[s["id"]], full_pad, 1.0)
        for s in source_slides
    }
    kept = select_slides(source_slides, durations_full, outro_duration, video_cfg)

    pad = full_pad
    lead_in = settings.NARRATION_LEAD_IN
    speed = 1.0
    if _plan_total(kept, reads, speeches, full_pad, 1.0, outro_duration) > max_seconds:
        pad = floor_pad
        lead_in = settings.NARRATION_LEAD_IN_FLOOR
        if _plan_total(kept, reads, speeches, floor_pad, 1.0, outro_duration) > max_seconds:
            speed = _fit_speed(
                kept, reads, speeches, floor_pad, outro_duration, max_seconds
            )
    return kept, pad, lead_in, speed


def build_render_plan(job, explainer, narration=None):
    video_cfg = video_settings(job)
    source_slides = explainer.get("slides", [])
    content_format = explainer.get("explainer", {}).get(
        "content_format", settings.DEFAULT_CONTENT_FORMAT
    )
    outro_speech = _speech_duration(narration, "outro")
    outro_narrated = video_cfg["outro_enabled"] and outro_speech > 0
    if not video_cfg["outro_enabled"]:
        outro_duration = 0.0
    elif outro_narrated:
        # Grow the card so the spoken call-to-action is never clipped.
        outro_duration = max(
            settings.DEFAULT_OUTRO_DURATION,
            round(
                settings.NARRATION_LEAD_IN
                + outro_speech
                + settings.NARRATION_TAIL_PAD,
                2,
            ),
        )
    else:
        outro_duration = settings.DEFAULT_OUTRO_DURATION
    reads = {
        slide["id"]: natural_duration(slide, content_format)
        for slide in source_slides
    }

    narration_speed = 1.0
    narration_lead_in = 0.0
    if narration and narration.get("slides"):
        speeches = {
            slide["id"]: _speech_duration(narration, slide["id"])
            for slide in source_slides
        }
        kept, pad, narration_lead_in, narration_speed = build_narration_timing(
            source_slides, reads, speeches, outro_duration, video_cfg
        )
        durations = {
            s["id"]: _voiced_duration(
                reads[s["id"]], speeches[s["id"]], pad, narration_speed
            )
            for s in kept
        }
        scale = 1.0
        absorb_overflow = False
    else:
        speeches = {slide["id"]: 0.0 for slide in source_slides}
        kept = select_slides(source_slides, reads, outro_duration, video_cfg)
        scale = scale_to_range(kept, reads, outro_duration, video_cfg)
        durations = {s["id"]: reads[s["id"]] * scale for s in kept}
        absorb_overflow = True

    slides = []
    cursor = 0.0
    for slide in kept:
        duration = round(durations[slide["id"]], 2)
        slides.append(
            {
                "id": slide["id"],
                "role": slide["role"],
                "word_count": (
                    word_count(slide.get("heading"))
                    + word_count(slide.get("explanation"))
                ),
                "narrated": speeches[slide["id"]] > 0,
                "start": round(cursor, 2),
                "end": round(cursor + duration, 2),
                "duration": duration,
            }
        )
        cursor += duration
    # Silent (word-count) timing rounds per slide and can nudge the plan a
    # hundredth of a second over the cap; absorb that in the last content slide.
    # Never do this when audio drives timing: it would clip a spoken line.
    max_content_duration = video_cfg["max_seconds"] - outro_duration
    if absorb_overflow and slides and cursor > max_content_duration:
        overflow = round(cursor - max_content_duration, 2)
        slides[-1]["duration"] = round(slides[-1]["duration"] - overflow, 2)
        slides[-1]["end"] = round(slides[-1]["end"] - overflow, 2)
        cursor -= overflow
    if outro_duration:
        slides.append(
            {
                "id": "outro",
                "role": "outro",
                "narrated": outro_narrated,
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
            "voiceover": bool(narration and narration.get("slides")),
            "narration_speed": round(narration_speed, 3),
            "narration_lead_in": round(narration_lead_in, 3),
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
    if plan["params"]["voiceover"]:
        print(
            f"  voice-over timing: speed x{narration_speed:.2f}, "
            f"lead-in {narration_lead_in:.2f}s"
        )
        if cursor > video_cfg["max_seconds"] + 0.05:
            over = cursor - video_cfg["max_seconds"]
            note = "" if over <= settings.OVERFLOW_TOLERANCE else " (over tolerance)"
            print(
                f"  WARNING: plan runs {over:.1f}s over max_seconds "
                f"({video_cfg['max_seconds']}s){note}"
            )
    if plan["dropped_slides"]:
        print(f"  dropped optional slides: {plan['dropped_slides']}")
    return plan
