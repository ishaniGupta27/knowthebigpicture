from pathlib import Path

from PIL import Image, ImageDraw

from .compose import W, H, load_font, draw_centered
from .errors import KtwError
from .job import video_settings
from .narrate import compress_narration
from . import settings


def make_outro_card(path):
    """Fallback branded outro if no outro asset is supplied."""
    image = Image.new("RGB", (W, H), (14, 15, 18))
    draw = ImageDraw.Draw(image)
    cx = W // 2

    promise_font = load_font(int(W * 0.058))
    brand_font = load_font(int(W * 0.040))
    cta_font = load_font(int(W * 0.034))

    draw_centered(draw, cx, int(H * 0.42), "Understand the what.", promise_font, (255, 255, 255))
    draw_centered(draw, cx, int(H * 0.42) + int(W * 0.07), "Discover the why and how.",
                  promise_font, (255, 255, 255))
    draw_centered(draw, cx, int(H * 0.56), settings.BRAND_SIGNATURE, brand_font,
                  (176, 190, 210))
    draw_centered(draw, cx, int(H * 0.62), "Follow to understand the world.", cta_font,
                  (150, 150, 150))

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=92)
    return path


def resolve_outro(job, cfg):
    if not cfg["outro_enabled"]:
        return None
    configured = job.section("video").get("outro", {}).get("image")
    if configured:
        candidate = job.root / configured
        if candidate.is_file():
            return candidate
    if settings.DEFAULT_OUTRO_IMAGE.is_file():
        return settings.DEFAULT_OUTRO_IMAGE
    # Generate a fallback card so the pipeline always has a proper closer.
    fallback = job.outputs_dir / "outro_fallback.jpg"
    print("  outro asset not found; generating a fallback brand card")
    return make_outro_card(fallback)


def ken_burns(clip, duration, motion):
    if motion <= 0:
        return clip
    try:
        from moviepy import CompositeVideoClip

        zoomed = clip.resized(lambda t: 1 + motion * (t / duration))
        zoomed = zoomed.with_position("center")
        return CompositeVideoClip([zoomed], size=(W, H)).with_duration(duration)
    except Exception as e:
        print(f"  (motion disabled for a slide: {e})")
        return clip


def slide_clip(frame_path, duration, motion):
    from moviepy import ImageClip

    if not Path(frame_path).is_file():
        raise KtwError(f"Frame missing for render: {frame_path}")
    clip = ImageClip(str(frame_path)).with_duration(duration)
    return ken_burns(clip, duration, motion)


def resolve_audio_track(cfg):
    track = cfg["audio_track"]
    if not track:
        if settings.DEFAULT_AUDIO_TRACK.is_file():
            return settings.DEFAULT_AUDIO_TRACK
        return None
    track_path = Path(track)
    if not track_path.is_absolute() and not track_path.is_file():
        # audio_track in job.json is relative to the assets dir if not found local.
        track_path = settings.ASSETS_DIR / track
    if not track_path.is_file():
        print(f"  audio track not found ({track})")
        return None
    return track_path


def _music_clip(track_path, total_duration, volume):
    from moviepy import AudioFileClip, afx

    audio = AudioFileClip(str(track_path))
    audio = audio.with_effects([afx.AudioLoop(duration=total_duration)])
    return audio.with_effects([afx.MultiplyVolume(volume)])


def attach_audio(final, cfg, total_duration):
    track_path = resolve_audio_track(cfg)
    if track_path is None:
        return final, False
    try:
        return final.with_audio(
            _music_clip(track_path, total_duration, cfg["audio_volume"])
        ), True
    except Exception as e:
        print(f"  audio attach failed ({e}); rendering silent")
        return final, False


def _narration_clips(job, render_plan, narration, speed, lead_in):
    from moviepy import AudioFileClip

    compressed_dir = job.narration_dir / "compressed"
    clips = []
    for slide in render_plan["slides"]:
        if not slide.get("narrated"):
            continue
        entry = (narration.get("slides") or {}).get(str(slide["id"]))
        if not entry:
            continue
        src = job.narration_dir / entry["file"]
        if not src.is_file():
            print(f"  narration clip missing for slide {slide['id']}; skipping")
            continue
        path = src
        if speed > 1.001:
            path = compress_narration(src, compressed_dir / entry["file"], speed)
        clip = AudioFileClip(str(path))
        clips.append(clip.with_start(round(slide["start"] + lead_in, 3)))
    return clips


def attach_voiceover_audio(job, final, cfg, render_plan, narration, total_duration):
    """Mix per-slide narration over ducked background music."""
    from moviepy import CompositeAudioClip

    params = render_plan.get("params", {})
    speed = float(params.get("narration_speed", 1.0))
    lead_in = float(params.get("narration_lead_in", 0.0))
    try:
        tracks = _narration_clips(job, render_plan, narration, speed, lead_in)
        if not tracks:
            print("  no narration clips available; falling back to music-only")
            return attach_audio(final, cfg, total_duration)
        track_path = resolve_audio_track(cfg)
        if track_path is not None:
            music_volume = cfg["voiceover"]["music_volume"]
            tracks.append(_music_clip(track_path, total_duration, music_volume))
        composite = CompositeAudioClip(tracks).with_duration(total_duration)
        return final.with_audio(composite), True
    except Exception as e:
        print(f"  voice-over mix failed ({e}); falling back to music-only")
        return attach_audio(final, cfg, total_duration)


def run_video(job, explainer, render_plan, narration=None):
    """Stage 5b: stitch explainer frames into a vertical video."""
    from moviepy import concatenate_videoclips

    cfg = video_settings(job)
    slides = [s for s in render_plan["slides"] if s["role"] != "outro"]

    clips = []
    for slide in slides:
        frame_path = job.frames_dir / f"{slide['id']}.jpg"
        clips.append(slide_clip(frame_path, slide["duration"], cfg["motion"]))

    outro_path = resolve_outro(job, cfg)
    if outro_path is not None:
        outro_slide = next(
            (s for s in render_plan["slides"] if s["role"] == "outro"), None
        )
        outro_duration = (
            outro_slide["duration"] if outro_slide else settings.DEFAULT_OUTRO_DURATION
        )
        clips.append(slide_clip(outro_path, outro_duration, 0))

    if not clips:
        raise KtwError("No slides to render")

    print(f"Stitching {len(clips)} clips into video")
    final = concatenate_videoclips(clips, method="compose")
    use_voiceover = bool(
        narration
        and narration.get("slides")
        and render_plan.get("params", {}).get("voiceover")
    )
    if use_voiceover:
        final, has_audio = attach_voiceover_audio(
            job, final, cfg, render_plan, narration, final.duration
        )
    else:
        final, has_audio = attach_audio(final, cfg, final.duration)

    job.video_path.parent.mkdir(parents=True, exist_ok=True)
    write_kwargs = {
        "fps": settings.VIDEO_FPS,
        "codec": settings.VIDEO_CODEC,
        "ffmpeg_params": settings.FFMPEG_EXTRA_PARAMS,
        "logger": None,
    }
    if has_audio:
        write_kwargs["audio_codec"] = settings.AUDIO_CODEC
    else:
        write_kwargs["audio"] = False

    final.write_videofile(str(job.video_path), **write_kwargs)
    final.close()

    print(f"Video written: {job.video_path}")
    return str(job.video_path)
