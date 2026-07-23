import json

from .job import parse_settings, video_settings
from . import settings


def word_count(text):
    return len((text or "").split())


def natural_duration(node):
    base = settings.TIMING_BASE_BEAT + word_count(node.get("headline")) * settings.TIMING_PER_WORD
    if node.get("role") == settings.ROLE_RESOLUTION:
        base += settings.TIMING_RESOLUTION_BONUS
    return max(base, settings.TIMING_READING_FLOOR)


def select_nodes(nodes, durations, outro_duration, cfg_video, min_developments):
    """Drop lowest-priority developments if we exceed the max length."""
    kept = list(nodes)

    def total():
        return sum(durations[n["id"]] for n in kept) + outro_duration

    while total() > cfg_video["max_seconds"]:
        developments = [n for n in kept if n.get("role") == settings.ROLE_DEVELOPMENT]
        if len(developments) <= min_developments:
            break
        # Drop the least essential development (highest priority number).
        drop = max(developments, key=lambda n: (n.get("priority", 2), n["id"]))
        kept = [n for n in kept if n["id"] != drop["id"]]

    return kept


def scale_to_range(kept, durations, outro_duration, cfg_video):
    content = sum(durations[n["id"]] for n in kept)
    total = content + outro_duration
    scale = 1.0
    if total > cfg_video["max_seconds"] and content > 0:
        scale = (cfg_video["max_seconds"] - outro_duration) / content
    elif total < cfg_video["min_seconds"] and content > 0:
        scale = (cfg_video["min_seconds"] - outro_duration) / content
    return scale


def build_render_plan(job, timeline):
    """Stage 5a: derive per-slide timing (natural length within a range)."""
    parse_cfg = parse_settings(job)
    video_cfg = video_settings(job)
    nodes = timeline.get("nodes", [])

    outro_duration = (
        settings.DEFAULT_OUTRO_DURATION if video_cfg["outro_enabled"] else 0.0
    )
    durations = {node["id"]: natural_duration(node) for node in nodes}

    kept = select_nodes(
        nodes, durations, outro_duration, video_cfg, parse_cfg["min_developments"]
    )
    scale = scale_to_range(kept, durations, outro_duration, video_cfg)

    slides = []
    cursor = 0.0
    for node in kept:
        duration = round(durations[node["id"]] * scale, 2)
        slides.append(
            {
                "id": node["id"],
                "role": node["role"],
                "word_count": word_count(node.get("headline")),
                "start": round(cursor, 2),
                "end": round(cursor + duration, 2),
                "duration": duration,
            }
        )
        cursor += duration

    if outro_duration > 0:
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

    plan = {
        "generated_from": "timeline.json",
        "params": {
            "base_beat": settings.TIMING_BASE_BEAT,
            "per_word": settings.TIMING_PER_WORD,
            "reading_floor": settings.TIMING_READING_FLOOR,
            "min_seconds": video_cfg["min_seconds"],
            "max_seconds": video_cfg["max_seconds"],
            "scale_applied": round(scale, 3),
        },
        "dropped_nodes": [
            n["id"] for n in nodes if n["id"] not in {k["id"] for k in kept}
        ],
        "slides": slides,
        "total_duration": round(cursor, 2),
    }

    job.render_plan_path.parent.mkdir(parents=True, exist_ok=True)
    with job.render_plan_path.open("w") as f:
        json.dump(plan, f, indent=2)
        f.write("\n")

    print(f"Render plan: {len(slides)} slides, {plan['total_duration']}s total")
    if plan["dropped_nodes"]:
        print(f"  dropped low-priority nodes: {plan['dropped_nodes']}")
    return plan
