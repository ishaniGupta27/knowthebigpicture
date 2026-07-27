import argparse
import sys

from .env import load_dotenv_if_present
from .errors import KtwError
from .instagram import publish_reel
from .job import load_job
from .remote import rclone_bin_from_env, remote_root_from_env
from . import settings


def main(argv=None):
    load_dotenv_if_present()
    parser = argparse.ArgumentParser(
        description="Publish a rendered Know the Big Picture job as an Instagram Reel."
    )
    parser.add_argument("job_id", help="Numeric job id (folder under jobs/).")
    parser.add_argument("--jobs-dir", default=None, help="Override the local jobs dir.")
    parser.add_argument(
        "--remote-root",
        default=None,
        help="rclone remote root used to build the public video URL "
        "(defaults to KBP_REMOTE_ROOT).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Publish again even if instagram_upload.json already exists.",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    jobs_root = args.jobs_dir or settings.jobs_dir()
    remote_root = args.remote_root or remote_root_from_env()

    try:
        job = load_job(args.job_id, jobs_root)
        publish_reel(
            job,
            remote_root=remote_root,
            rclone_bin=rclone_bin_from_env(),
            force=args.force,
        )
    except KtwError as e:
        print(f"ERROR: {e}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
