import argparse
import sys

from .env import load_dotenv_if_present
from .errors import KtwError
from .job import load_job
from . import settings
from .youtube import publish_short


def main(argv=None):
    load_dotenv_if_present()
    parser = argparse.ArgumentParser(
        description="Publish a rendered Know the Big Picture job as a private YouTube Short."
    )
    parser.add_argument("job_id", help="Numeric job id (folder under jobs/).")
    parser.add_argument("--jobs-dir", default=None, help="Override the local jobs dir.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Upload again even if youtube_upload.json already exists.",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    jobs_root = args.jobs_dir or settings.jobs_dir()

    try:
        job = load_job(args.job_id, jobs_root)
        publish_short(job, force=args.force)
    except KtwError as e:
        print(f"ERROR: {e}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
