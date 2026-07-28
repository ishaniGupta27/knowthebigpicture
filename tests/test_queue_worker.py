import importlib.util
import os
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "queue_worker.py"
SPEC = importlib.util.spec_from_file_location("queue_worker", MODULE_PATH)
queue_worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(queue_worker)


class FakeQueue:
    def __init__(self, rows):
        self.headers = list(queue_worker.REQUIRED_HEADERS)
        self.rows = []
        for row_number, source in enumerate(rows, start=2):
            row = {header: "" for header in self.headers}
            row.update(source)
            row["_row_number"] = row_number
            self.rows.append(row)

    def read_rows(self):
        return self.headers, self.rows

    def update_row(self, headers, row):
        self.rows[row["_row_number"] - 2] = row


class QueueWorkerTests(unittest.TestCase):
    def test_claim_ignores_new_and_claims_lowest_pending_id(self):
        queue = FakeQueue(
            [
                {"id": "1", "status": "new", "format": "why", "topic": "A"},
                {"id": "5", "status": "pending", "format": "how", "topic": "B"},
                {
                    "id": "2",
                    "status": "pending",
                    "format": "types",
                    "topic": "Types of rice",
                    "number_of_items": "5",
                    "youtube_public": "TRUE",
                },
            ]
        )
        with tempfile.NamedTemporaryFile() as output:
            previous = os.environ.get("GITHUB_OUTPUT")
            os.environ["GITHUB_OUTPUT"] = output.name
            try:
                queue_worker.command_claim(queue)
            finally:
                if previous is None:
                    os.environ.pop("GITHUB_OUTPUT", None)
                else:
                    os.environ["GITHUB_OUTPUT"] = previous
            output.seek(0)
            outputs = output.read().decode()

        self.assertEqual(queue.rows[0]["status"], "new")
        self.assertEqual(queue.rows[1]["status"], "pending")
        self.assertEqual(queue.rows[2]["status"], "processing")
        self.assertIn("job_id", outputs)
        self.assertIn("\n2\n", outputs)
        self.assertIn("youtube_public", outputs)
        self.assertIn("\ntrue\n", outputs)

    def test_invalid_pending_row_fails_without_blocking_next_valid_row(self):
        queue = FakeQueue(
            [
                {"id": "1", "status": "pending", "format": "wrong", "topic": "A"},
                {"id": "2", "status": "pending", "format": "why", "topic": "B"},
            ]
        )
        queue_worker.command_claim(queue)
        self.assertEqual(queue.rows[0]["status"], "failed")
        self.assertIn("format must be one of", queue.rows[0]["error"])
        self.assertEqual(queue.rows[0]["retry_count"], "1")
        self.assertEqual(queue.rows[1]["status"], "processing")

    def test_complete_and_fail_update_status_fields(self):
        queue = FakeQueue(
            [{"id": "8", "status": "processing", "format": "why", "topic": "A"}]
        )
        queue_worker.command_complete(queue, "8", "https://example.com/video")
        self.assertEqual(queue.rows[0]["status"], "done")
        self.assertEqual(queue.rows[0]["output_url"], "https://example.com/video")
        self.assertTrue(queue.rows[0]["completed_at"])

        queue_worker.command_fail(queue, "8", "retry this")
        self.assertEqual(queue.rows[0]["status"], "failed")
        self.assertEqual(queue.rows[0]["retry_count"], "1")
        self.assertEqual(queue.rows[0]["error"], "retry this")


if __name__ == "__main__":
    unittest.main()
