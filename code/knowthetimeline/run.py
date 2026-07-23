import argparse
import sys

from .env import load_dotenv_if_present
from .errors import KttError
from .job import load_job
from .remote import (
    pull_remote_inputs,
    push_remote_job,
    rclone_bin_from_env,
    remote_root_from_env,
)
from .runlog import run_log_path, tee_to_log
from .runner import run_job
from . import settings


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="KnowTheTimeline: build a chronological Short from a source document."
    )
    parser.add_argument("job_id", help="Numeric job id (folder under jobs/).")
    parser.add_argument(
        "--jobs-dir",
        default=None,
        help="Override the local jobs directory (default: <repo>/jobs).",
    )
    parser.add_argument(
        "--remote",
        nargs="?",
        const="__env__",
        default=None,
        help="Sync the job folder with remote storage before/after the run. "
        "Optionally pass a remote root (e.g. gdrive:knowthetimeline).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the full pipeline offline with mocked LLM/image calls.",
    )
    parser.add_argument(
        "--no-publish",
        action="store_true",
        help="Never publish to YouTube even if youtube.enabled is true.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore cached timeline.json and re-run parsing.",
    )
    return parser.parse_args(argv)


def resolve_remote_root(value):
    if value is None:
        return None
    if value == "__env__":
        root = remote_root_from_env()
        if not root:
            raise KttError(
                "--remote given without a root and KTT_REMOTE_ROOT is not set."
            )
        return root
    return value


def main(argv=None):
    load_dotenv_if_present()
    args = parse_args(argv if argv is not None else sys.argv[1:])

    jobs_root = args.jobs_dir or settings.jobs_dir()
    remote_root = resolve_remote_root(args.remote)
    rclone_bin = rclone_bin_from_env()

    log_path = run_log_path(jobs_root, args.job_id)
    try:
        with tee_to_log(log_path):
            if remote_root:
                pull_remote_inputs(
                    args.job_id,
                    remote_root,
                    jobs_root,
                    settings.ASSETS_DIR,
                    rclone_bin,
                )

            job = load_job(args.job_id, jobs_root)
            run_job(
                job,
                dry_run=args.dry_run,
                publish=not args.no_publish,
                force=args.force,
            )

            if remote_root:
                push_remote_job(args.job_id, remote_root, jobs_root, rclone_bin)
    except KttError as e:
        print(f"ERROR: {e}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
