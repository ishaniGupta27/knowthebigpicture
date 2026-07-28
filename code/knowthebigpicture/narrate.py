"""Stage 2c: synthesize per-slide voice-over narration.

Produces one audio clip per content slide and a manifest describing each clip's
duration, so the render plan can drive slide timing from real speech length. The
stage degrades gracefully: if synthesis is unavailable or fails, and the job's
``on_tts_fail`` is ``"music"``, it returns ``None`` and the pipeline renders the
original silent-slides + looped-music video instead.
"""

import asyncio
import hashlib
import json
import subprocess

from .job import video_settings
from . import settings


def _slide_text(slide):
    narration = (slide.get("narration") or "").strip()
    if narration:
        return narration
    parts = [slide.get("heading"), slide.get("explanation")]
    return ". ".join(part.strip() for part in parts if (part or "").strip())


def _voice_hash(text, voice, rate, engine):
    payload = f"{engine}\n{voice}\n{rate}\n{text}".encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def measure_duration(path):
    from moviepy import AudioFileClip

    clip = AudioFileClip(str(path))
    try:
        return float(clip.duration)
    finally:
        clip.close()


def _synthesize_edge(text, voice, rate, out_path):
    import edge_tts

    async def _run():
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(str(out_path))

    asyncio.run(_run())


def _synthesize(engine, text, voice, rate, out_path):
    if engine == "edge":
        _synthesize_edge(text, voice, rate, out_path)
        return
    raise NarrationError(f"Unsupported voiceover engine: {engine}")


class NarrationError(RuntimeError):
    pass


def compress_narration(src_path, dst_path, factor):
    """Time-compress an audio file while preserving pitch (ffmpeg atempo)."""
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(src_path),
            "-filter:a",
            f"atempo={factor:.4f}",
            str(dst_path),
        ],
        check=True,
        capture_output=True,
    )
    return dst_path


def load_manifest(job):
    if not job.narration_manifest_path.is_file():
        return None
    try:
        return json.loads(job.narration_manifest_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _build_manifest(job, explainer, cfg, force):
    engine = cfg["engine"]
    voice = cfg["voice"]
    rate = cfg["rate"]
    job.narration_dir.mkdir(parents=True, exist_ok=True)
    previous = {} if force else ((load_manifest(job) or {}).get("slides") or {})

    slides = {}
    for slide in explainer.get("slides", []):
        slide_id = str(slide["id"])
        text = _slide_text(slide)
        if not text:
            continue
        text_hash = _voice_hash(text, voice, rate, engine)
        audio_path = job.narration_dir / f"{slide_id}.mp3"
        cached = previous.get(slide_id)
        if (
            not force
            and cached
            and cached.get("hash") == text_hash
            and audio_path.is_file()
        ):
            duration = float(cached["duration"])
            print(f"  slide {slide_id}: cached narration ({duration:.2f}s)")
        else:
            print(f"  slide {slide_id}: synthesizing narration")
            _synthesize(engine, text, voice, rate, audio_path)
            duration = measure_duration(audio_path)
            print(f"  slide {slide_id}: {duration:.2f}s")
        slides[slide_id] = {
            "file": audio_path.name,
            "duration": round(duration, 3),
            "hash": text_hash,
            "text": text,
        }

    manifest = {
        "engine": engine,
        "voice": voice,
        "rate": rate,
        "slides": slides,
    }
    job.narration_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    job.narration_manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def run_narrate(job, explainer, force=False):
    """Synthesize narration; return the manifest or None to fall back to music."""
    cfg = video_settings(job)["voiceover"]
    if not cfg["enabled"]:
        print("Voice-over disabled; using music-only audio.")
        return None
    try:
        manifest = _build_manifest(job, explainer, cfg, force)
    except (NarrationError, subprocess.CalledProcessError, OSError, ImportError) as exc:
        if cfg["on_tts_fail"] == "fail_job":
            raise NarrationError(f"Narration synthesis failed: {exc}") from exc
        print(f"  narration failed ({exc}); falling back to music-only audio")
        return None
    if not manifest["slides"]:
        print("  no narration produced; falling back to music-only audio")
        return None
    total = sum(entry["duration"] for entry in manifest["slides"].values())
    print(
        f"Narration ready: {len(manifest['slides'])} clips, {total:.1f}s spoken "
        f"(voice: {cfg['voice']})"
    )
    return manifest


def mock_narrate(job, explainer, force=False):
    """Dry-run: skip TTS so timing falls back to the word-count model."""
    print("[dry-run] skipping narration synthesis")
    return None
