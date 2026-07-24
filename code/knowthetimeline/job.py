import json
from dataclasses import dataclass, field
from pathlib import Path

from .errors import KttError
from . import settings


@dataclass
class Job:
    job_id: str
    root: Path
    config: dict
    inputs_dir: Path
    source_path: Path
    headline_path: Path
    outputs_dir: Path
    logs_dir: Path
    status_path: Path
    timeline_path: Path
    metadata_path: Path
    content_path: Path
    render_plan_path: Path
    backgrounds_dir: Path
    frames_dir: Path
    video_path: Path

    def section(self, name):
        value = self.config.get(name, {})
        if not isinstance(value, dict):
            raise KttError(f"job.json section '{name}' must be an object")
        return value

    def get(self, section, key, default):
        return self.section(section).get(key, default)


def load_job(job_id, jobs_root):
    root = Path(jobs_root) / str(job_id)
    if not root.is_dir():
        raise KttError(f"Job folder does not exist: {root}")

    config_path = root / "job.json"
    config = {}
    if config_path.is_file():
        try:
            with config_path.open("r") as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            raise KttError(f"Invalid job.json: {e}") from e
        if not isinstance(config, dict):
            raise KttError("job.json must contain a JSON object")

    source_path = root / "inputs" / "source.txt"
    outputs_dir = root / "outputs"

    job = Job(
        job_id=str(job_id),
        root=root,
        config=config,
        inputs_dir=root / "inputs",
        source_path=source_path,
        headline_path=root / "inputs" / "headline.txt",
        outputs_dir=outputs_dir,
        logs_dir=root / "logs",
        status_path=root / "status.json",
        timeline_path=outputs_dir / "timeline.json",
        metadata_path=outputs_dir / "youtube_metadata.json",
        content_path=outputs_dir / "content.json",
        render_plan_path=outputs_dir / "render_plan.json",
        backgrounds_dir=outputs_dir / "backgrounds",
        frames_dir=outputs_dir / "frames",
        video_path=outputs_dir / "timeline.mp4",
    )

    validate_job(job)
    return job


def validate_job(job):
    if not job.source_path.is_file() and not job.headline_path.is_file():
        raise KttError(
            f"Missing required author input under {job.inputs_dir}. "
            "Provide inputs/source.txt, or inputs/headline.txt to have the "
            "source generated (step 0)."
        )

    for name in ("story", "parse", "images", "compose", "video", "youtube", "instagram"):
        if name in job.config and not isinstance(job.config[name], dict):
            raise KttError(f"job.json section '{name}' must be an object")


# --- Typed config accessors (all with global defaults) -----------------------

def parse_settings(job):
    parse = job.section("parse")
    return {
        "model": parse.get("model") or settings.DEFAULT_PARSE_MODEL,
        "min_developments": int(
            parse.get("min_developments", settings.DEFAULT_MIN_DEVELOPMENTS)
        ),
        "max_developments": int(
            parse.get("max_developments", settings.DEFAULT_MAX_DEVELOPMENTS)
        ),
        "max_words_per_headline": int(
            parse.get("max_words_per_headline", settings.MAX_WORDS_PER_HEADLINE)
        ),
        "grounding": parse.get("grounding", "dates_only"),
        "on_verification_fail": parse.get("on_verification_fail", "fail_job"),
    }


def image_settings(job):
    images = job.section("images")
    model = images.get("model") or settings.DEFAULT_IMAGE_MODEL
    return {
        "model": model,
        "vibe": images.get("vibe"),  # None -> default_vibe from styles.json
        "size": images.get("size") or settings.image_size_for_model(model),
    }


def compose_settings(job):
    compose = job.section("compose")
    return {
        "backdrop": compose.get("backdrop", settings.DEFAULT_BACKDROP),
        "blur_radius": int(compose.get("blur_radius", settings.DEFAULT_BLUR_RADIUS)),
        "plate_opacity": float(
            compose.get("plate_opacity", settings.DEFAULT_PLATE_OPACITY)
        ),
        "show_date_kicker": bool(
            compose.get("show_date_kicker", settings.DEFAULT_SHOW_DATE_KICKER)
        ),
        "show_detail": bool(compose.get("show_detail", settings.DEFAULT_SHOW_DETAIL)),
    }


def video_settings(job):
    video = job.section("video")
    outro = video.get("outro", {})
    if not isinstance(outro, dict):
        raise KttError("video.outro must be an object")
    audio_track = video.get("audio_track")
    return {
        "min_seconds": float(video.get("min_seconds", settings.DEFAULT_MIN_SECONDS)),
        "max_seconds": float(video.get("max_seconds", settings.DEFAULT_MAX_SECONDS)),
        "motion": float(video.get("motion", settings.DEFAULT_MOTION)),
        "transition": video.get("transition", settings.DEFAULT_TRANSITION),
        "audio_track": audio_track,
        "audio_volume": float(
            video.get("audio_volume", settings.DEFAULT_AUDIO_VOLUME)
        ),
        "outro_enabled": bool(outro.get("enabled", True)),
    }


def story_overrides(job):
    story = job.section("story")
    return {
        "topic": story.get("topic"),
        "central_question": story.get("central_question"),
    }


def youtube_settings(job):
    return job.section("youtube")


def instagram_settings(job):
    return job.section("instagram")
