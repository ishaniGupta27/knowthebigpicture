import json
from pathlib import Path
import tempfile
import unittest

from knowthebigpicture.create_job import create_job, parse_args
from knowthebigpicture.job import load_job
from knowthebigpicture.youtube import validate_youtube_config


class QueueJobTests(unittest.TestCase):
    def create(self, root, *extra):
        args = parse_args(
            [
                "41",
                "--question",
                "Why is Himalayan salt pink?",
                "--format",
                "why",
                "--jobs-dir",
                str(root),
                *extra,
            ]
        )
        return create_job(args)

    def test_private_youtube_is_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.create(root)
            job = load_job("41", root)
            youtube = validate_youtube_config(job)
            self.assertTrue(youtube["enabled"])
            self.assertEqual(youtube["privacy_status"], "private")

    def test_youtube_public_flag_creates_public_job(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job_root = self.create(root, "--youtube-public")
            config = json.loads((job_root / "job.json").read_text())
            self.assertEqual(config["youtube"]["privacy_status"], "public")
            job = load_job("41", root)
            self.assertEqual(
                validate_youtube_config(job)["privacy_status"],
                "public",
            )


if __name__ == "__main__":
    unittest.main()
