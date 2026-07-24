from .compose import run_compose
from .content import write_content
from .dry_run import mock_images, mock_parse
from .images import run_images
from .job import youtube_settings
from .parse import run_parse
from .renderplan import build_render_plan
from .sourcegen import ensure_source
from .status import write_status
from .verify import run_verify
from .video import run_video
from .youtube import publish_short


def log_section(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def log_kv(label, value):
    print(f"{label}: {value}")


def run_job(job, dry_run=False, publish=True, force=False, lite=False):
    job.outputs_dir.mkdir(parents=True, exist_ok=True)
    job.logs_dir.mkdir(parents=True, exist_ok=True)
    write_status(job, "running", dry_run=dry_run, lite=lite)

    log_section("KNOWTHETIMELINE JOB")
    log_kv("Job ID", job.job_id)
    log_kv("Job folder", job.root)
    log_kv("Dry run", dry_run)
    log_kv("Lite (content only)", lite)

    try:
        log_section("STAGE 0  SOURCE")
        ensure_source(job, dry_run=dry_run)

        log_section("STAGE 1  PARSE")
        timeline = mock_parse(job, force=force) if dry_run else run_parse(job, force=force)

        log_section("STAGE 2  VERIFY")
        timeline = run_verify(job, timeline)

        log_section("STAGE 2b  CONTENT")
        content_path = write_content(job, timeline)

        if lite:
            outputs = {
                "timeline": str(job.timeline_path),
                "metadata": str(job.metadata_path),
                "content": str(content_path),
                "lite": True,
            }
            print("\nLITE run: stopping after content (no images, video, or publish).")
            write_status(job, "done", dry_run=dry_run, lite=lite, outputs=outputs)
            log_section("DONE")
            for key, value in outputs.items():
                log_kv(key, value)
            return outputs

        log_section("STAGE 3  IMAGES")
        image_results = mock_images(job, timeline) if dry_run else run_images(job, timeline)

        log_section("STAGE 4  COMPOSE")
        frames = run_compose(job, timeline)

        log_section("STAGE 5  RENDER")
        render_plan = build_render_plan(job, timeline)
        video_path = run_video(job, timeline, render_plan)

        outputs = {
            "timeline": str(job.timeline_path),
            "metadata": str(job.metadata_path),
            "content": str(content_path),
            "render_plan": str(job.render_plan_path),
            "backgrounds": len(image_results),
            "frames": len(frames),
            "video": video_path,
            "total_duration": render_plan["total_duration"],
        }

        youtube = youtube_settings(job)
        if publish and not dry_run and youtube.get("enabled", False):
            log_section("STAGE 6  PUBLISH")
            result_path = publish_short(job)
            outputs["youtube_upload"] = str(result_path)
        else:
            reason = "dry-run" if dry_run else (
                "not requested" if not publish else "youtube.enabled is false"
            )
            print(f"\nSTAGE 6  PUBLISH skipped ({reason})")

    except Exception as e:
        write_status(job, "failed", dry_run=dry_run, error=str(e))
        raise

    write_status(job, "done", dry_run=dry_run, outputs=outputs)

    log_section("DONE")
    for key, value in outputs.items():
        log_kv(key, value)
    return outputs
