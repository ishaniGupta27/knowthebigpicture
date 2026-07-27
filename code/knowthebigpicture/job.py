import json
from dataclasses import dataclass
from pathlib import Path

from .errors import KtwError
from . import settings


@dataclass
class Job:
    job_id: str
    root: Path
    config: dict
    inputs_dir: Path
    source_path: Path
    question_path: Path
    outputs_dir: Path
    logs_dir: Path
    status_path: Path
    explainer_path: Path
    metadata_path: Path
    content_path: Path
    render_plan_path: Path
    backgrounds_dir: Path
    frames_dir: Path
    video_path: Path

    def section(self, name):
        value = self.config.get(name, {})
        if not isinstance(value, dict):
            raise KtwError(f"job.json section '{name}' must be an object")
        return value


def load_job(job_id, jobs_root):
    root = Path(jobs_root) / str(job_id)
    if not root.is_dir():
        raise KtwError(f"Job folder does not exist: {root}")

    config = {}
    config_path = root / "job.json"
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text())
        except json.JSONDecodeError as exc:
            raise KtwError(f"Invalid job.json: {exc}") from exc
        if not isinstance(config, dict):
            raise KtwError("job.json must contain a JSON object")

    outputs_dir = root / "outputs"
    job = Job(
        job_id=str(job_id),
        root=root,
        config=config,
        inputs_dir=root / "inputs",
        source_path=root / "inputs" / "source.txt",
        question_path=root / "inputs" / "question.txt",
        outputs_dir=outputs_dir,
        logs_dir=root / "logs",
        status_path=root / "status.json",
        explainer_path=outputs_dir / "explainer.json",
        metadata_path=outputs_dir / "youtube_metadata.json",
        content_path=outputs_dir / "content.json",
        render_plan_path=outputs_dir / "render_plan.json",
        backgrounds_dir=outputs_dir / "backgrounds",
        frames_dir=outputs_dir / "frames",
        video_path=outputs_dir / "explainer.mp4",
    )
    validate_job(job)
    return job


def validate_job(job):
    if not job.source_path.is_file() and not job.question_path.is_file():
        raise KtwError(
            f"Missing input under {job.inputs_dir}. Provide inputs/question.txt, "
            "with optional inputs/source.txt."
        )
    for name in ("explainer", "parse", "images", "compose", "video", "youtube", "instagram"):
        if name in job.config and not isinstance(job.config[name], dict):
            raise KtwError(f"job.json section '{name}' must be an object")


def parse_settings(job):
    parse = job.section("parse")
    return {
        "model": parse.get("model") or settings.DEFAULT_PARSE_MODEL,
        "min_slides": int(parse.get("min_slides", settings.DEFAULT_MIN_SLIDES)),
        "max_slides": int(parse.get("max_slides", settings.DEFAULT_MAX_SLIDES)),
        "max_words_per_heading": int(
            parse.get("max_words_per_heading", settings.MAX_WORDS_PER_HEADING)
        ),
        "max_words_per_explanation": int(
            parse.get("max_words_per_explanation", settings.MAX_WORDS_PER_EXPLANATION)
        ),
        "on_verification_fail": parse.get("on_verification_fail", "fail_job"),
    }


def image_settings(job):
    images = job.section("images")
    model = images.get("model") or settings.DEFAULT_IMAGE_MODEL
    return {
        "model": model,
        "vibe": images.get("vibe"),
        "size": images.get("size") or settings.image_size_for_model(model),
    }


def compose_settings(job):
    compose = job.section("compose")
    return {
        "backdrop": compose.get("backdrop", settings.DEFAULT_BACKDROP),
        "blur_radius": int(compose.get("blur_radius", settings.DEFAULT_BLUR_RADIUS)),
        "plate_opacity": float(compose.get("plate_opacity", settings.DEFAULT_PLATE_OPACITY)),
        "show_explanation": bool(
            compose.get("show_explanation", settings.DEFAULT_SHOW_EXPLANATION)
        ),
        "show_role_kicker": bool(
            compose.get("show_role_kicker", settings.DEFAULT_SHOW_ROLE_KICKER)
        ),
    }


def video_settings(job):
    video = job.section("video")
    outro = video.get("outro", {})
    if not isinstance(outro, dict):
        raise KtwError("video.outro must be an object")
    return {
        "min_seconds": float(video.get("min_seconds", settings.DEFAULT_MIN_SECONDS)),
        "max_seconds": float(video.get("max_seconds", settings.DEFAULT_MAX_SECONDS)),
        "motion": float(video.get("motion", settings.DEFAULT_MOTION)),
        "transition": video.get("transition", settings.DEFAULT_TRANSITION),
        "audio_track": video.get("audio_track"),
        "audio_volume": float(video.get("audio_volume", settings.DEFAULT_AUDIO_VOLUME)),
        "outro_enabled": bool(outro.get("enabled", True)),
    }


def explainer_overrides(job):
    cfg = job.section("explainer")
    return {
        "question": cfg.get("question"),
        "subject": cfg.get("subject"),
        "audience": cfg.get("audience", "general_non_technical_audience"),
    }


def youtube_settings(job):
    return job.section("youtube")


def instagram_settings(job):
    return job.section("instagram")
