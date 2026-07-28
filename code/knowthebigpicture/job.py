import json
import re
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
    narration_dir: Path
    narration_manifest_path: Path
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
        narration_dir=outputs_dir / "narration",
        narration_manifest_path=outputs_dir / "narration" / "narration.json",
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
    explainer = explainer_overrides(job)
    if explainer["content_format"] == settings.FORMAT_TYPES:
        expected_slides = explainer["item_count"] + 1
        default_min_slides = expected_slides
        default_max_slides = expected_slides
    else:
        default_min_slides = settings.DEFAULT_MIN_SLIDES
        default_max_slides = settings.DEFAULT_MAX_SLIDES
    provider = parse.get("provider") or settings.DEFAULT_LLM_PROVIDER
    if provider not in settings.VALID_LLM_PROVIDERS:
        available = ", ".join(settings.VALID_LLM_PROVIDERS)
        raise KtwError(f"parse.provider must be one of: {available}")
    return {
        "provider": provider,
        "model": parse.get("model") or settings.DEFAULT_PARSE_MODEL,
        "gemini_model": parse.get("gemini_model") or settings.DEFAULT_GEMINI_MODEL,
        "temperature": float(
            parse.get("temperature", settings.DEFAULT_LLM_TEMPERATURE)
        ),
        "min_slides": int(parse.get("min_slides", default_min_slides)),
        "max_slides": int(parse.get("max_slides", default_max_slides)),
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
    provider = images.get("provider") or settings.DEFAULT_IMAGE_PROVIDER
    if provider not in settings.VALID_LLM_PROVIDERS:
        available = ", ".join(settings.VALID_LLM_PROVIDERS)
        raise KtwError(f"images.provider must be one of: {available}")
    model = images.get("model") or settings.DEFAULT_IMAGE_MODEL
    return {
        "provider": provider,
        "model": model,
        "gemini_model": images.get("gemini_model")
        or settings.DEFAULT_GEMINI_IMAGE_MODEL,
        "vibe": images.get("vibe"),
        "size": images.get("size") or settings.image_size_for_model(model),
        "aspect_ratio": images.get("aspect_ratio")
        or settings.DEFAULT_IMAGE_ASPECT_RATIO,
        "quality": images.get("quality") or settings.DEFAULT_IMAGE_QUALITY,
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
        "voiceover": voiceover_settings(job),
    }


def voiceover_settings(job):
    video = job.section("video")
    cfg = video.get("voiceover", {})
    if not isinstance(cfg, dict):
        raise KtwError("video.voiceover must be an object")
    return {
        "enabled": bool(cfg.get("enabled", settings.DEFAULT_VOICEOVER_ENABLED)),
        "engine": cfg.get("engine") or settings.DEFAULT_TTS_ENGINE,
        "voice": cfg.get("voice") or settings.DEFAULT_TTS_VOICE,
        "rate": cfg.get("rate") or settings.DEFAULT_TTS_RATE,
        "music_volume": float(
            cfg.get("music_volume", settings.DEFAULT_VOICEOVER_MUSIC_VOLUME)
        ),
        "on_tts_fail": cfg.get("on_tts_fail") or settings.DEFAULT_ON_TTS_FAIL,
        "outro_narration": (
            cfg["outro_narration"]
            if "outro_narration" in cfg
            else settings.DEFAULT_OUTRO_NARRATION
        ),
    }


def explainer_overrides(job):
    cfg = job.section("explainer")
    content_format = cfg.get("content_format", settings.DEFAULT_CONTENT_FORMAT)
    if content_format not in settings.VALID_CONTENT_FORMATS:
        available = ", ".join(settings.VALID_CONTENT_FORMATS)
        raise KtwError(
            f"explainer.content_format must be one of: {available}"
        )
    item_count = settings.DEFAULT_TYPES_ITEM_COUNT
    if content_format == settings.FORMAT_TYPES:
        configured_item_count = cfg.get("item_count")
        if configured_item_count is not None:
            item_count = int(configured_item_count)
        else:
            input_text = cfg.get("question") or ""
            if not input_text and job.question_path.is_file():
                input_text = job.question_path.read_text().strip()
            leading_count = re.match(r"^\s*(\d+)\b", input_text)
            item_count = (
                int(leading_count.group(1))
                if leading_count
                else settings.DEFAULT_TYPES_ITEM_COUNT
            )
    if (
        content_format == settings.FORMAT_TYPES
        and not settings.MIN_TYPES_ITEM_COUNT
        <= item_count
        <= settings.MAX_TYPES_ITEM_COUNT
    ):
        raise KtwError(
            "explainer.item_count must be between "
            f"{settings.MIN_TYPES_ITEM_COUNT} and {settings.MAX_TYPES_ITEM_COUNT}"
        )
    return {
        "question": cfg.get("question"),
        "subject": cfg.get("subject"),
        "audience": cfg.get("audience", "general_non_technical_audience"),
        "content_format": content_format,
        "item_count": item_count,
    }


def youtube_settings(job):
    return job.section("youtube")


def instagram_settings(job):
    return job.section("instagram")
