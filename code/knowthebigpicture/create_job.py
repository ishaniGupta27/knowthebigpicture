import argparse
import json
from pathlib import Path
import sys

from .errors import KtwError
from . import settings


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Create a Know the Big Picture job from queue or CLI input."
    )
    parser.add_argument("job_id")
    parser.add_argument("--question", required=True)
    parser.add_argument(
        "--format",
        dest="content_format",
        choices=settings.VALID_CONTENT_FORMATS,
        required=True,
    )
    parser.add_argument("--item-count", type=int)
    parser.add_argument("--youtube-public", action="store_true")
    parser.add_argument("--instagram", action="store_true")
    parser.add_argument("--jobs-dir", default=None)
    return parser.parse_args(argv)


def create_job(args):
    if not str(args.job_id).isdigit():
        raise KtwError("job_id must be numeric")
    question = args.question.strip()
    if not question:
        raise KtwError("question must not be empty")
    if args.item_count is not None:
        if args.content_format != settings.FORMAT_TYPES:
            raise KtwError("--item-count is only valid with --format types")
        if not settings.MIN_TYPES_ITEM_COUNT <= args.item_count <= settings.MAX_TYPES_ITEM_COUNT:
            raise KtwError(
                f"--item-count must be {settings.MIN_TYPES_ITEM_COUNT}-"
                f"{settings.MAX_TYPES_ITEM_COUNT}"
            )

    jobs_root = Path(args.jobs_dir or settings.jobs_dir())
    root = jobs_root / str(args.job_id)
    question_path = root / "inputs" / "question.txt"
    if question_path.is_file() and question_path.read_text().strip() != question:
        raise KtwError(
            f"Job {args.job_id} already belongs to a different question"
        )

    explainer = {
        "content_format": args.content_format,
        "audience": "general_non_technical_audience",
    }
    if args.item_count is not None:
        explainer["item_count"] = args.item_count

    config = {
        "explainer": explainer,
        "youtube": {
            "enabled": True,
            "upload_type": "short",
            "privacy_status": "public" if args.youtube_public else "private",
            "category_id": "27",
            "made_for_kids": False,
            "contains_synthetic_media": True,
        },
        "instagram": {
            "enabled": bool(args.instagram),
            "publish_mode": "container_only",
        },
    }
    question_path.parent.mkdir(parents=True, exist_ok=True)
    question_path.write_text(question + "\n")
    (root / "job.json").write_text(json.dumps(config, indent=2) + "\n")
    print(f"Job created: {root}")
    return root


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    try:
        create_job(args)
    except KtwError as exc:
        print(f"ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
